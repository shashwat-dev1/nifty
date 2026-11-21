"""Provenanced daily archive, reproducible astronomical features and daily evaluation."""
import csv
import hashlib
import io
import json
import math
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import requests
import swisseph as swe

from kp_engine import KPChart, PLANETS, IDS, IST, sign_lord, star_lord, sub_lord, LAT, LON
from research import FACTORS

ROOT = Path(__file__).resolve().parent / "archive"
RAW = ROOT / "raw"
DB = ROOT / "research.duckdb"
MODEL = "KP-VBA-0.1/" + swe.version + "/" + hashlib.sha256(Path(__file__).with_name("kp_engine.py").read_bytes()).hexdigest()[:12]
NAMES = {"S&P CNX NIFTY":"NIFTY 50","CNX NIFTY":"NIFTY 50","NIFTY 50":"NIFTY 50","INDIA VIX":"INDIA VIX"}
OFFICIAL = "https://archives.nseindia.com/content/indices/ind_close_all_{:%d%m%Y}.csv"

def connect(path=DB):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=duckdb.connect(str(path))
    db.execute("SET TimeZone='Asia/Kolkata'")
    db.execute("""CREATE TABLE IF NOT EXISTS daily(instrument VARCHAR, day DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
        provider VARCHAR, raw_file VARCHAR, quality VARCHAR, imported_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(instrument,day))""")
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots(ts TIMESTAMPTZ,model VARCHAR,lat DOUBLE,lon DOUBLE,details VARCHAR,
        PRIMARY KEY(ts,model,lat,lon))""")
    db.execute("CREATE TABLE IF NOT EXISTS sync_log(day DATE,status VARCHAR,detail VARCHAR,attempt TIMESTAMPTZ DEFAULT now())")
    db.execute("""CREATE OR REPLACE VIEW trading_dates AS SELECT day,provider FROM daily WHERE instrument='NIFTY 50'""")
    db.execute("""CREATE VIEW IF NOT EXISTS kp_signatures AS SELECT ts,model,lat,lon,json_extract_string(details,'$.signature') AS signature,
       CAST(json_extract(details,'$.kp_score') AS DOUBLE) AS score FROM snapshots""")
    db.execute("""CREATE VIEW IF NOT EXISTS planetary_positions AS SELECT ts,model,lat,lon,body.key AS planet,
       body.value AS state FROM snapshots, json_each(details,'$.positions') body""")
    return db

def parse_report(content,expected,source,name):
    rows=[]
    for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig"))):
        instrument=NAMES.get(row["Index Name"].strip().upper())
        if not instrument: continue
        day=datetime.strptime(row["Index Date"].strip().replace("/","-"),"%d-%m-%Y").date()
        if day!=expected: raise ValueError(f"Report for {day} under {expected}")
        close=float(row["Closing Index Value"])
        if not math.isfinite(close) or close<=0: raise ValueError("Invalid closing level")
        o,h,l=[pd.to_numeric(row.get(k+" Index Value"),errors="coerce") for k in ("Open","High","Low")]
        quality="OHLC"
        if not (0<l<=min(o,close)<=max(o,close)<=h and l<h and np.isfinite(h)):
            o=h=l=None
            quality="Close only"
        if day<date(1996,4,22) and instrument=="NIFTY 50": quality+=" · pre-launch history"
        rows.append((instrument,day,o,h,l,close,source,name,quality))
    if len({r[0] for r in rows})!=len(rows): raise ValueError("Duplicate instrument in report")
    return rows

COLS=["instrument","day","open","high","low","close","provider","raw_file","quality"]
def insert_daily(db,rows):
    if not rows:return
    incoming=pd.DataFrame(rows,columns=COLS)
    conflicts=db.execute("""SELECT i.day,i.instrument FROM incoming i JOIN daily d USING(instrument,day)
      WHERE abs(d.close-i.close)>0.005 OR abs(d.open-i.open)>0.005 OR abs(d.high-i.high)>0.005 OR abs(d.low-i.low)>0.005""").fetchall()
    if conflicts: raise ValueError(f"Price conflict {conflicts[:3]}")
    db.execute("INSERT INTO daily BY NAME SELECT * FROM incoming ON CONFLICT DO NOTHING")

def import_bundle(db,folder):
    rows=[]
    for p in sorted(folder.rglob("*.csv")):
        day=date.fromisoformat(p.stem)
        try: rows.extend(parse_report(p.read_bytes(),day,"NSE via PowerNSE",str(p.relative_to(ROOT))))
        except (ValueError,KeyError) as e:
            db.execute("INSERT INTO sync_log(day,status,detail) VALUES(?, 'quarantined', ?)",[day,str(e)])
    insert_daily(db,rows)

def sync(db,start,end):
    for t in pd.date_range(start,end):
        day=t.date()
        fn=RAW/f"nse-{day}.csv"
        url=OFFICIAL.format(day)
        try:
            if fn.exists(): content=fn.read_bytes()
            else:
                r=requests.get(url,timeout=12)
                if r.status_code in (403,429):
                    raise RuntimeError(f"Provider returned {r.status_code}. Resume later. Retry-After: {r.headers.get('Retry-After','unspecified')}")
                r.raise_for_status()
                content=r.content
                time.sleep(.25)
            rows=parse_report(content,day,"NSE archive",str(fn.relative_to(ROOT)))
            if not any(row[0]=="NIFTY 50" for row in rows): raise ValueError("No spot-index observation")
            fn.write_bytes(content)
            insert_daily(db,rows)
            status="validated"
            msg=url
        except (requests.RequestException,ValueError,RuntimeError) as e:
            status="unavailable"
            msg=str(e)
        db.execute("INSERT INTO sync_log(day,status,detail) VALUES(?,?,?)",[day,status,msg])
        yield day,status
        if "Resume later" in msg:break

def detailed(t,lat=LAT,lon=LON):
    chart=KPChart(t,lat,lon)
    value=chart.calculate()
    value["positions"]={}
    for name in PLANETS:
        x=chart.longitude(name)
        state,flags=swe.calc_ut(chart.jd,IDS.get(name,swe.MEAN_NODE),chart.flags)
        value["positions"][name]=dict(longitude=x,speed=state[3],retrograde=state[3]<0,nakshatra=int(x/(360/27))+1,
            star=star_lord(x),sub=sub_lord(x),sign=sign_lord(x),houses=sorted(chart.significator_houses(name)),flags=flags)
    return json.dumps(value,separators=(",",":"))

def build(db,times,lat=LAT,lon=LON):
    times=pd.DatetimeIndex(times).unique()
    if not len(times):return
    if times.tz is None:raise ValueError("Timezone required")
    existing=db.execute("SELECT ts FROM snapshots WHERE model=? AND lat=? AND lon=? AND ts BETWEEN ? AND ?",[MODEL,lat,lon,times.min(),times.max()]).df()
    missing=times.difference(existing.ts)
    for i in range(0,len(missing),256):
        chunk=missing[i:i+256]
        batch=pd.DataFrame(dict(ts=chunk,model=MODEL,lat=lat,lon=lon,details=[detailed(t,lat,lon) for t in chunk]))
        db.execute("INSERT INTO snapshots SELECT * FROM batch ON CONFLICT DO NOTHING")
        yield min(i+256,len(missing)),len(missing)

def cached(db,start,end,lat=LAT,lon=LON,decision=None):
    fields=[f"json_extract_string(details,'$.ruling_planets.{k}') AS {k}" for k in FACTORS]
    fields += [f"json_extract_string(details,'$.ruling_details[{i}].class') AS {k}_classification" for i,k in enumerate(FACTORS)]
    fields += [f"CAST(json_extract(details,'$.positions.{p}.longitude') AS DOUBLE) AS {p}" for p in PLANETS]
    fields += [f"CAST(json_extract(details,'$.components.B{i}') AS DOUBLE) AS B{i}" for i in range(12,19)]
    condition=" AND ts::TIMESTAMP::TIME=CAST(? AS TIME)" if decision is not None else ""
    return db.execute("""SELECT ts AS timestamp,CAST(json_extract(details,'$.kp_score') AS DOUBLE) AS score,
        json_extract_string(details,'$.majority') AS majority,"""+",".join(fields)+
        " FROM snapshots WHERE CAST(ts AS DATE) BETWEEN ? AND ? AND model=? AND lat=? AND lon=?"+condition+" ORDER BY ts",
        [start,end,MODEL,lat,lon]+([str(decision)] if decision is not None else [])).df()

def daily_outcomes(prices,horizon):
    # Signal at midnight before session opens. Entry at observed open and exit at the h-th observed session close.
    frame=prices.sort_values("day").copy()
    frame["exit_day"]=frame.day.shift(1-horizon)
    frame["exit_price"]=frame.close.shift(1-horizon)
    frame["return_pct"]=100*(frame.exit_price/frame.open-1)
    return frame

def walk_forward(rows,key,minimum,first_year,horizon):
    rows=rows.sort_values("day").dropna(subset=["return_pct"]).copy()
    rows["actual"]=np.sign(rows.return_pct)
    folds=[]
    for year in sorted(rows.day.dt.year.unique()):
        if year<first_year:continue
        cut=pd.Timestamp(year=year,month=1,day=1)
        train=rows[rows.exit_day<cut]
        test=rows[rows.day.dt.year==year]
        if train.empty:continue
        counts=train.groupby(key).actual.agg(["count",lambda v:v.mode().iat[0]])
        counts.columns=["training_n","prediction"]
        matched=test.join(counts[counts.training_n>=minimum],on=key,how="inner").sort_values("day")
        matched["baseline"]=train.actual.mode().iat[0]
        folds.append(matched)
    if not folds:return pd.DataFrame()
    result=pd.concat(folds).sort_values("day")
    keep=[]
    last=None
    for row in result.itertuples():
        if last is None or row.day>last:
            keep.append(row.Index)
            last=row.exit_day
    return result.loc[keep].copy()


def save_report(db,kind,frame,parameters):
    from uuid import uuid4
    folder=ROOT/"reports"
    folder.mkdir(exist_ok=True)
    name=f"{kind}-{uuid4().hex}.parquet"
    path=folder/name
    frame.to_parquet(path,index=False)
    db.execute("""CREATE TABLE IF NOT EXISTS saved_reports(filename VARCHAR PRIMARY KEY,kind VARCHAR,parameters VARCHAR,records BIGINT,created_at TIMESTAMPTZ DEFAULT now())""")
    db.execute("INSERT INTO saved_reports(filename,kind,parameters,records) VALUES(?,?,?,?)",[name,kind,json.dumps(parameters),len(frame)])
    return name
