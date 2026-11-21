"""Authenticated forwarding target for the existing local dashboard."""
import asyncio
import aiohttp

TARGET="http://127.0.0.1:8520"
HOP={"host","connection","upgrade","keep-alive","transfer-encoding","content-length","accept-encoding","sec-websocket-key","sec-websocket-version","sec-websocket-protocol","sec-websocket-extensions","origin","x-forwarded-host","x-forwarded-proto"}
class DashboardProxy:
    async def __call__(self,scope,receive,send):
        if scope["type"]=="lifespan":
            while True:
                msg=await receive()
                await send({"type":msg["type"]+".complete"})
                if msg["type"]=="lifespan.shutdown":return
        if scope["path"]=="/":
            await send({"type":"http.response.start","status":303,"headers":[(b"location",b"/demo")]})
            return await send({"type":"http.response.body","body":b""})
        headers={k.decode():v.decode() for k,v in scope["headers"] if k.decode().lower() not in HOP}
        headers["Origin"]=TARGET
        path=scope.get("raw_path",scope["path"].encode()).decode("ascii")
        query=scope.get("query_string",b"").decode("ascii")
        path="/demo" if path=="/" else path
        url=TARGET+path+("?" + query if query else "")
        async with aiohttp.ClientSession(auto_decompress=False,timeout=aiohttp.ClientTimeout(total=None,sock_connect=5)) as client:
            if scope["type"]=="websocket":
                await receive()
                async with client.ws_connect(url,headers=headers,protocols=scope.get("subprotocols",[]),max_msg_size=32*1024*1024) as upstream:
                    await send({"type":"websocket.accept","subprotocol":upstream.protocol})
                    async def incoming():
                        while True:
                            msg=await receive()
                            if msg["type"]=="websocket.disconnect":return
                            if msg.get("bytes") is not None:await upstream.send_bytes(msg["bytes"])
                            elif msg.get("text") is not None:await upstream.send_str(msg["text"])
                    async def outgoing():
                        async for msg in upstream:
                            if msg.type==aiohttp.WSMsgType.BINARY:await send({"type":"websocket.send","bytes":msg.data})
                            elif msg.type==aiohttp.WSMsgType.TEXT:await send({"type":"websocket.send","text":msg.data})
                    tasks=[asyncio.create_task(incoming()),asyncio.create_task(outgoing())]
                    try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for task in tasks:task.cancel()
                        await asyncio.gather(*tasks,return_exceptions=True)
                return
            async def body():
                while True:
                    msg=await receive()
                    if msg["type"]=="http.disconnect":return
                    yield msg.get("body",b"")
                    if not msg.get("more_body"):return
            async with client.request(scope["method"],url,headers=headers,data=body(),allow_redirects=False) as response:
                response_headers=[(k,v) for k,v in response.raw_headers if k.decode().lower() not in {"transfer-encoding","connection"}]
                await send({"type":"http.response.start","status":response.status,"headers":response_headers})
                async for chunk in response.content.iter_chunked(65536):
                    await send({"type":"http.response.body","body":chunk,"more_body":True})
                await send({"type":"http.response.body","body":b""})
