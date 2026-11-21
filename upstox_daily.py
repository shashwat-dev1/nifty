"""Incremental daily index download; existing sources always retain precedence."""
from datetime import timedelta
import hashlib,json
import pandas as pd
from historical import connect,RAW,insert_daily
from kp_engine import IST
from upstox_history import fetch,verify_instrument

def sync_daily(token,start,end):
    verify_instrument()
    end=min(end,pd.Timestamp.now(tz=IST).date()-timedelta(days=1))
    with connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS broker_daily_batches(start_day DATE,end_day DATE,raw_file VARCHAR,received BIGINT,PRIMARY KEY(start_day,end_day))")
        con.execute("CREATE TABLE IF NOT EXISTS broker_daily_conflicts(day DATE,existing_close DOUBLE,incoming_close DOUBLE,raw_file VARCHAR,PRIMARY KEY(day,raw_file))")
        previous=con.sql("select start_day,end_day from broker_daily_batches").fetchall()
    while start<=end:
        covered=next((b for a,b in previous if a<=start<=b),None)
        if covered:start=covered+timedelta(days=1);continue
        last=min(start+timedelta(days=365),end)
        upcoming=[a for a,b in previous if start<a<=last]
        if upcoming:last=min(upcoming)-timedelta(days=1)
        body=fetch(token,start,last,unit="days")
        rows=[]
        raw=json.dumps(body).encode()
        name="upstox-daily-"+hashlib.sha256(raw).hexdigest()[:20]+".json"
        for candle in body["data"]["candles"]:
            stamp=pd.Timestamp(candle[0])
            if stamp.tzinfo is None:raise ValueError("Missing provider timezone")
            day=stamp.tz_convert(IST).date()
            o,h,l,c=map(float,candle[1:5])
            if not start<=day<=last or not 0<l<=min(o,c)<=max(o,c)<=h:raise ValueError("Invalid daily candle")
            rows.append(("NIFTY 50",day,o,h,l,c,"Upstox daily",name,"Broker API OHLC"))
        (RAW/name).write_bytes(raw)
        with connect() as con:
            con.execute("BEGIN")
            try:
                missing=[]
                for row in rows:
                    prior=con.execute("select open,high,low,close from daily where instrument=? and day=?",row[:2]).fetchone()
                    if prior is None:missing.append(row)
                    elif tuple(row[2:6])!=prior:con.execute("insert into broker_daily_conflicts values(?,?,?,?) on conflict do nothing",[row[1],prior[3],row[5],name])
                insert_daily(con,missing)
                con.execute("insert into broker_daily_batches values(?,?,?,?) on conflict do nothing",[start,last,name,len(rows)])
                con.execute("COMMIT")
            except Exception:con.execute("ROLLBACK");raise
        yield str(start),str(last),len(rows),len(missing)
        start=last+timedelta(days=1)
