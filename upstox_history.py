"""Read-only Upstox index candles. Times from provider denote bar starts."""
from datetime import timedelta
import gzip
import hashlib
import json
import time
from urllib.parse import quote
import pandas as pd
import requests
from historical import RAW
from kp_engine import IST
from research import prepare,save

KEY="NSE_INDEX|Nifty 50"
MASTER="https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
BASE="https://api.upstox.com/v3/historical-candle"
def verify_instrument():
    r=requests.get(MASTER,timeout=25)
    r.raise_for_status()
    for v in json.loads(gzip.decompress(r.content)):
        if v["instrument_key"]==KEY and v["segment"]=="NSE_INDEX" and v["instrument_type"]=="INDEX":
            return v
    raise ValueError("NIFTY 50 index identity missing from instrument master")

def fetch(token,start,end,current=False,unit="minutes"):
    path=f"{quote(KEY,safe='')}/{unit}/1"
    url=f"{BASE}/intraday/{path}" if current else f"{BASE}/{path}/{end}/{start}"
    for attempt in range(4):
        try:r=requests.get(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"},timeout=25)
        except requests.RequestException:
            if attempt==3:raise ValueError("Provider connection failed") from None
            time.sleep(2**attempt)
            continue
        if r.status_code not in (429,500,502,503,504) or attempt==3:break
        try:delay=float(r.headers.get("Retry-After",2**attempt))
        except ValueError:delay=2**attempt
        if delay>60:raise ValueError("Provider requested a long pause. Resume the download later.")
        time.sleep(max(1,delay))
    if r.status_code==429:raise ValueError("Rate limited. Retry after "+r.headers.get("Retry-After","the provider's reset"))
    if r.status_code!=200: raise ValueError(f"Upstox returned HTTP {r.status_code}. Check token, entitlement and range.")
    body=r.json()
    if body.get("status")!="success":raise ValueError("Unsuccessful provider response")
    return body

def normalize(body,start,end,now):
    rows=body["data"]["candles"]
    if not rows:return pd.DataFrame()
    df=pd.DataFrame([r[:5] for r in rows],columns=["timestamp","open","high","low","close"])
    if any(pd.Timestamp(s).tzinfo is None for s in df.timestamp):raise ValueError("Missing provider timezone")
    bars=prepare(df,{k:k for k in df},"Asia/Kolkata",1,True,True)
    if not bars.timestamp.dt.date.between(start,end).all():raise ValueError("Out-of-range provider candle")
    return bars[bars.timestamp<=now]

def sync_minutes(token,start,end,store,repair=False):
    verify_instrument()
    now=pd.Timestamp.now(tz=IST)
    end=min(end,now.date())
    from historical import connect
    with connect() as db:
        previous=db.execute("SELECT start_day,end_day FROM broker_batches WHERE end_day<?",[now.date()]).fetchall()
    if repair:previous=[]
    while start<=end:
        today=start==now.date()
        last=start if today else min(start+timedelta(days=27),end,now.date()-timedelta(days=1))
        covered=next((b for a,b in previous if a<=start<=b),None)
        if covered:
            start=covered+timedelta(days=1)
            continue
        upcoming=[a for a,b in previous if start<a<=last]
        if upcoming:last=min(upcoming)-timedelta(days=1)
        body=fetch(token,start,last,today)
        bars=normalize(body,start,last,now)
        if bars.empty and not today:
            name=f"upstox-empty-{start}-{last}.json"
            (RAW/name).write_text(json.dumps(body),encoding="utf-8")
            with connect() as db:
                db.execute("INSERT INTO broker_batches(start_day,end_day,raw_file,received) VALUES(?,?,?,0) ON CONFLICT DO NOTHING",[start,last,name])
        if len(bars):
            raw=json.dumps(body).encode()
            digest=hashlib.sha256(raw).hexdigest()[:14]
            name=f"upstox-{start}-{last}-{digest}.json"
            (RAW/name).write_bytes(raw)
            from minute_archive import store_bars
            from historical import connect
            with connect() as db:
                db.execute("BEGIN")
                try:
                    db.execute("""INSERT INTO broker_conflicts SELECT b.timestamp,?,i.close,b.close FROM bars b JOIN intraday i USING(timestamp)
                      WHERE i.close IS DISTINCT FROM b.close OR i.high IS DISTINCT FROM b.high OR i.low IS DISTINCT FROM b.low OR i.open IS DISTINCT FROM b.open
                      ON CONFLICT DO NOTHING""",[name])
                    missing=db.execute("SELECT b.* FROM bars b ANTI JOIN intraday i USING(timestamp)").df()
                    store_bars(db,missing,"Upstox 1m",name,"Broker API","start",1)
                    if not today:db.execute("INSERT INTO broker_batches(start_day,end_day,raw_file,received) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",[start,last,name,len(bars)])
                    db.execute("COMMIT")
                except Exception:
                    db.execute("ROLLBACK")
                    raise
        yield start,last,len(bars)
        start=last+timedelta(days=1)

