"""Windows session owner. The connector starts only after interactive approval."""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

import pywintypes
import win32api
import win32event
import win32job
import winerror
import requests
import uvicorn
from private_demo.data import prepare_snapshot
from private_demo.gate import COOKIE, SessionGate
from private_demo.install_connector import HOME, verified_binary

PROJECT=Path(__file__).resolve().parents[1]
EVENT=r"Local\NiftyKPPrivateDemoStop-"+hashlib.sha256(str(PROJECT).encode()).hexdigest()[:18]
FEEDBACK=HOME/"custom-feedback.sqlite3"

def protect_children():
    # Assign the owner before it spawns anything. Closing this process closes the
    # last job handle even on an abrupt console exit, terminating its children.
    job=win32job.CreateJobObject(None,"")
    limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
    limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
    win32job.AssignProcessToJobObject(job,win32api.GetCurrentProcess())
    # Let Windows close the handle after the owner has its final exit code.
    return job.Detach()

def stop():
    try:handle=win32event.OpenEvent(win32event.EVENT_MODIFY_STATE,False,EVENT)
    except pywintypes.error as exc:
        if exc.winerror==winerror.ERROR_FILE_NOT_FOUND:
            print("Private sharing is already stopped.")
            return
        raise
    win32event.SetEvent(handle)
    handle.Close()
    for _ in range(100):
        try:probe=win32event.OpenEvent(win32event.EVENT_MODIFY_STATE,False,EVENT)
        except pywintypes.error as exc:
            if exc.winerror==winerror.ERROR_FILE_NOT_FOUND:
                print("Private session stopped and access revoked.")
                return
            raise
        probe.Close()
        time.sleep(.1)
    raise RuntimeError("Stop requested. Confirm the owner window has closed.")

def owner_preflight(origin,password):
    http=requests.Session()
    http.trust_env=False
    def require(value,label):
        if not value:raise RuntimeError("Local security check failed: "+label)
    require(http.get(origin+"/api/health",timeout=5).status_code==401,"anonymous access denied")
    require(http.post(origin+"/login",headers={"Origin":origin},data={"password":"wrong"},allow_redirects=False,timeout=5).status_code==401,"incorrect password denied")
    response=http.post(origin+"/login",headers={"Origin":origin},data={"password":password},allow_redirects=False,timeout=5)
    require(response.status_code==303,"password login")
    headers={"Cookie":f"{COOKIE}={response.cookies[COOKIE]}"}
    require(http.get(origin+"/",headers=headers,allow_redirects=False,timeout=5).status_code==303,"demo redirect")
    require(http.get(origin+"/demo",headers=headers,timeout=5).status_code==200,"frontend")
    require(http.get(origin+"/api/health",headers=headers,timeout=5).json()["status"]=="ok","API health")
    daily=http.get(origin+'/api/daily-research?day=2026-11-25',headers=headers,timeout=20)
    require(daily.status_code==200 and len(daily.json().get('timeline',[]))==26,'full-day KP movement')
    slots=http.get(origin+'/api/kp/slot-matches?timestamp=2026-11-25T12:30:00%2B05:30',headers=headers,timeout=30)
    require(slots.status_code==200 and 'total' in slots.json(),'exact six-factor slot matching')
    for path in ["/api/admin/feedback","/api/admin/sync","/api/admin/import","/api/admin/jobs","/api/backtest"]:
        require(http.get(origin+path,headers=headers,timeout=5).status_code==403,"admin denied "+path)
        require(http.post(origin+path,headers={**headers,"Origin":origin},json={},timeout=5).status_code==403,"admin writes denied "+path)
    for path in ["/archive/research.duckdb","/custom_api.py","/.env"]:
        require(http.get(origin+path,headers=headers,timeout=5).status_code==404,"file denied")
    result=http.post(origin+"/api/calculate",headers={**headers,"Origin":origin},json={"timestamp":"2026-11-20T10:30:00+05:30"},timeout=5)
    require(result.status_code==200 and len(result.json()["rows"])==9,"authenticated calculation")


def monitor(command,gate,stopped,password,show=print,timeout=65):
    """Own exactly one connector; revoke the gate before terminating it."""
    messages=queue.Queue()
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(("TUNNEL_","CLOUDFLARED_","UPSTOX","STREAMLIT_"))}
    with subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          text=True,encoding="utf8",errors="replace",env=env,creationflags=subprocess.CREATE_NO_WINDOW) as child:
        def read_lines():
            for line in child.stdout:
                url=re.search(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b",line)
                if url:messages.put(url.group(0))
        threading.Thread(target=read_lines,daemon=True).start()
        started=time.monotonic()
        announced=False
        try:
            while not stopped() and time.time()<gate.expires:
                if child.poll() is not None:raise RuntimeError(f"Connector exited with code {child.returncode}.")
                if not announced:
                    try:url=messages.get_nowait()
                    except queue.Empty:
                        if time.monotonic()-started>timeout:raise RuntimeError("No HTTPS URL received from Cloudflare. Check internet access.")
                    else:
                        gate.origin=url
                        show(f"SHARING ACTIVE · password authentication enabled\nLink: {url}\nTemporary password: {password}\nExpires: {datetime.fromtimestamp(gate.expires).astimezone():%Y-%m-%d %H:%M %Z}\nSend the link and password separately. Keep this window open.")
                        announced=True
                time.sleep(.15)
        finally:
            gate.expires=0
            gate.token_hash=None
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=4)
                except subprocess.TimeoutExpired:child.kill()
    show("Sharing stopped. This session's password and browser access have expired.")

def serve(check=False):
    event=win32event.CreateEvent(None,True,False,EVENT)
    if win32api.GetLastError()==winerror.ERROR_ALREADY_EXISTS:raise RuntimeError("A demo session is already running.")
    stopped=lambda: win32event.WaitForSingleObject(event,0)==win32event.WAIT_OBJECT_0
    connector=verified_binary()
    hours=24 if check else float(input("Duration in hours [24, maximum 48]: ").strip() or "24")
    if not 0<hours<=48:raise ValueError("Choose a duration greater than zero and at most 48 hours.")
    # Keep handle until process termination, including unexpected termination.
    global _job
    try:
        requests.get("http://127.0.0.1:8520/api/health",timeout=2).raise_for_status()
    except requests.RequestException:
        subprocess.Popen([sys.executable,"-m","uvicorn","custom_api:app","--host","127.0.0.1","--port","8520"],
            cwd=PROJECT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        for attempt in range(100):
            try:
                requests.get("http://127.0.0.1:8520/api/health",timeout=1).raise_for_status()
                break
            except requests.RequestException:time.sleep(.1)
        else:raise RuntimeError("Owner dashboard did not start on port 8520.")
    _job=protect_children()
    HOME.mkdir(parents=True,exist_ok=True)
    # The proxy connects to the same running dashboard, preserving its database owner.
    response=requests.get("http://127.0.0.1:8520/api/health",timeout=3)
    response.raise_for_status()
    from private_demo.proxy import DashboardProxy
    with tempfile.TemporaryDirectory(prefix="session-",dir=HOME) as folder, closing(socket.socket()) as sock:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        sock.bind(("127.0.0.1",0))
        sock.listen()
        origin=f"http://127.0.0.1:{sock.getsockname()[1]}"
        password=secrets.token_urlsafe(24)
        gate=SessionGate(DashboardProxy(),password,time.time()+hours*3600,origin,owner=False)
        server=uvicorn.Server(uvicorn.Config(gate,host="127.0.0.1",port=sock.getsockname()[1],access_log=False,proxy_headers=False,
                            ws_max_size=32768,ws_max_queue=8,timeout_graceful_shutdown=2,log_level="warning"))
        thread=threading.Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
        thread.start()
        try:
            deadline=time.monotonic()+25
            while not server.started:
                if time.monotonic()>deadline or not thread.is_alive():raise RuntimeError("Demo server failed to start")
                time.sleep(.05)
            owner_preflight(origin,password)
            gate.token_hash=None
            print("Local checks passed: login and protected forwarding to the owner dashboard.")
            if check:return
            print("OFFLINE · Read-only custom dashboard with protected administration.")
            if input("Confirm you permit this friend to view the available market data (type DATA): ").strip()!="DATA":
                print("Sharing cancelled.")
                return
            print("The next step shares the existing dashboard through Cloudflare.")
            if input("Type SHARE to approve this temporary internet session: ").strip()!="SHARE" or stopped():
                print("Cancelled locally.")
                return
            gate.expires=time.time()+hours*3600
            cfg=Path(folder)/"connector.yml"
            cfg.write_text("loglevel: info\n",encoding="ascii")
            monitor([str(connector),"tunnel","--config",str(cfg),"--no-autoupdate","--metrics","127.0.0.1:0","--url",origin],gate,lambda:stopped() or not thread.is_alive(),password)
        finally:
            gate.expires=0
            server.should_exit=True
            thread.join(5)
            event.Close()

def review():
    if not FEEDBACK.exists():
        print("No tester feedback yet.")
        return
    with closing(sqlite3.connect(FEEDBACK.as_uri()+"?mode=ro",uri=True)) as db:
        for row in db.execute("SELECT created,feature,expected,actual,comments FROM feedback ORDER BY rowid DESC"):
            for label,value in zip(("UTC","Feature","Expected","Actual","Comments"),row):
                print(label+": "+"".join(c for c in value if c.isprintable() or c=="\n"))
            print()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["start","stop","check","feedback"])
    action=parser.parse_args().action
    try:
        if action=="stop":stop()
        elif action=="feedback":review()
        else:serve(action=="check")
    except (Exception,KeyboardInterrupt) as exc:
        print(f"Private demo: {exc}")
        sys.exit(1)


