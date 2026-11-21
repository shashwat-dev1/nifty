"""Origin, login, expiry and protocol checks outside the whole Streamlit ASGI app."""
import asyncio
from collections import deque
import hashlib
import hmac
import secrets
import time
from urllib.parse import parse_qs
from starlette.requests import HTTPConnection, Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse

COOKIE="__Host-kp-demo"
LOGIN="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Private NIFTY research session</title>
<style>body{background:#101820;color:#f5f7f9;font:18px system-ui;max-width:26rem;margin:12vh auto;padding:1.5rem}input,button{box-sizing:border-box;width:100%;padding:.8rem;margin:.6rem 0 1rem;font:inherit}button{background:#b5efcb;border:0;border-radius:.3rem}</style>
<h1>Private research session</h1><form method="post" action="/login"><label>Temporary access password<input type="password" name="password" autocomplete="current-password" maxlength="128" required></label><button>Open terminal</button></form></html>"""
HEADERS={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff","Referrer-Policy":"same-origin","X-Frame-Options":"DENY","Strict-Transport-Security":"max-age=86400"}
def verifier(password,salt):
    return hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32)

class SessionGate:
    def __init__(self,app,password,expires,local_origin,owner=False):
        self.owner=owner
        self.app=app
        self.expires=expires
        self.origin=local_origin
        self.salt=secrets.token_bytes(16)
        self.verifier=verifier(password,self.salt)
        self.token_hash=None
        self.failures=deque()
        self.sockets=0

    def authorized(self,token):
        if not self.token_hash or not token or len(token)>128:return False
        return time.time()<self.expires and hmac.compare_digest(hashlib.sha256(token.encode()).digest(),self.token_hash)

    async def login(self,scope,receive,send):
        request=Request(scope,receive)
        if request.method=="GET":
            res=HTMLResponse(LOGIN,headers={**HEADERS,"Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"})
        elif request.method!="POST" or request.headers.get("origin")!=self.origin:
            res=PlainTextResponse("Forbidden",403,headers=HEADERS)
        else:
            now=time.monotonic()
            while self.failures and now-self.failures[0]>60:self.failures.popleft()
            if len(self.failures)>=6:
                res=PlainTextResponse("Please retry in one minute.",429,headers=HEADERS)
            else:
                buf=bytearray()
                async for part in request.stream():
                    if len(buf)+len(part)>512:
                        return await PlainTextResponse("Too large",413)(scope,receive,send)
                    buf.extend(part)
                fields=parse_qs(buf.decode("utf8",errors="replace"))
                pw=fields.get("password",[""])[0]
                if not hmac.compare_digest(verifier(pw,self.salt),self.verifier):
                    self.failures.append(now)
                    res=PlainTextResponse("Incorrect password. Return to the login page to retry.",401,headers=HEADERS)
                else:
                    token=secrets.token_urlsafe(32)
                    self.token_hash=hashlib.sha256(token.encode()).digest()
                    self.failures.clear()
                    res=RedirectResponse("/",303,headers=HEADERS)
                    res.set_cookie(COOKIE,token,secure=True,httponly=True,samesite="strict",max_age=max(0,int(self.expires-time.time())))
        await res(scope,receive,send)

    async def __call__(self,scope,receive,send):
        if scope["type"]=="lifespan":
            return await self.app(scope,receive,send)
        conn=HTTPConnection(scope)
        ws=scope["type"]=="websocket"
        path=scope["path"]
        async def reject(code):
            if ws:await send({"type":"websocket.close","code":1008})
            else:await PlainTextResponse("Access unavailable",code,headers=HEADERS)(scope,receive,send)
        if time.time()>=self.expires:return await reject(410)
        if conn.headers.get("host")!=self.origin.split("://",1)[1]:return await reject(403)
        if self.origin.startswith("https://") and conn.headers.get("x-forwarded-proto")!="https":return await reject(403)
        if not ws and path=="/login":return await self.login(scope,receive,send)
        token=conn.cookies.get(COOKIE)
        if not self.authorized(token):
            if not ws and path=="/":return await RedirectResponse("/login",303,headers=HEADERS)(scope,receive,send)
            return await reject(401)
        if ws:return await reject(403)
        if path.startswith("/api/admin") or path=="/api/backtest":return await reject(403)
        allowed_get=path in ("/","/demo","/api/health","/api/coverage","/api/upstox","/api/studies","/api/candles","/api/timeline") or (path.startswith("/assets/") and ".." not in path)
        allowed_post=path in ("/api/calculate","/api/matches","/api/statistics","/api/feedback")
        if scope["method"] in ("GET","HEAD") and not allowed_get:return await reject(404)
        if scope["method"] not in ("GET","HEAD"):
            if scope["method"]!="POST" or not allowed_post or conn.headers.get("origin")!=self.origin:return await reject(403)
        async def protected_send(msg):
            if msg["type"]=="http.response.start":
                headers=[(k,v) for k,v in msg.get("headers",[]) if k.lower()!=b"cache-control"]
                msg={**msg,"headers":headers+[(k.lower().encode(),v.encode()) for k,v in HEADERS.items()]}
            await send(msg)
        await self.app(scope,receive,protected_send)
