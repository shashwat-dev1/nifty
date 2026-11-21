"""Local custom terminal API. The existing KP mathematics remains the source of truth."""
from datetime import date,datetime,time as clock,timedelta
from pathlib import Path
from typing import Literal
import json,os,threading,uuid
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import duckdb
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator,model_validator
from kp_engine import KPChart,IST,LAT,LON,PLANETS,sub_lord,star_lord,sign_lord
from historical import DB,MODEL,build,detailed
from minute_archive import attach_prices
from research import FACTORS
from api_models import CalculationResponse,MatchResponse,CandleResponse
ROOT=Path(__file__).parent
LOCK=threading.RLock()
POOL=ThreadPoolExecutor(max_workers=1)
JOB_FILE=ROOT/"archive/custom-jobs.json"
try:JOBS=json.loads(JOB_FILE.read_text(encoding="utf-8"))
except (OSError,ValueError):JOBS={}
for old in JOBS.values():
    if old["status"] in ("queued","running"):old["status"]="interrupted; resubmit the same range to resume saved checkpoints"
JOB_LOCK=threading.RLock()
def save_jobs():
    with JOB_LOCK:
        temporary=JOB_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(JOBS),encoding="utf-8")
        temporary.replace(JOB_FILE)
app=FastAPI(title="NIFTY KP Terminal",docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","testserver"])
def db(write=False):
    con=duckdb.connect(str(DB))
    con.execute("SET TimeZone='Asia/Kolkata'")
    if not write:con.execute("BEGIN TRANSACTION READ ONLY")
    return con
def clean(df):return json.loads(df.to_json(orient="records",date_format="iso"))
def token():
    from keyring.backends.Windows import WinVaultKeyring
    return os.getenv("UPSTOX_ACCESS_TOKEN") or WinVaultKeyring().get_password("NIFTY KP Terminal","Upstox")
@app.middleware("http")
async def origin_guard(request:Request,call_next):
    if request.method not in ("GET","HEAD"):
        origin=request.headers.get("origin")
        if origin and origin!=str(request.base_url).rstrip("/"):
            return JSONResponse({"detail":"Origin rejected"},403)
    try:return await call_next(request)
    except (ValueError,duckdb.Error):return JSONResponse({"detail":"The operation could not be completed. Check the input or database availability."},400)
class Moment(BaseModel):
    timestamp:datetime
    @field_validator("timestamp")
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None:raise ValueError("Timezone required")
        if not 1900<=v.year<=2100:raise ValueError("Supported years 1900–2100")
        return v.astimezone(IST)
class Search(Moment):
    start:date=date(1995,11,3)
    end:date=date(2026,11,19)
    mode:Literal["exact","partial","sign","nakshatra","sub","score","longitude"]="exact"
    factors:list[Literal["day","moon_sign","moon_star","moon_sub","lagna"]]=FACTORS
    planets:list[Literal["Sun","Moon","Mars","Mercury","Venus","Jupiter","Saturn","Rahu","Ketu"]]=["Moon"]
    tolerance:float=Field(5,ge=0,le=180)
    minimum:float=-30
    maximum:float=30
    offset:int=Field(0,ge=0)
    limit:int=Field(25,ge=1,le=100)
    horizon:Literal[5,15,30,60]=15
    @model_validator(mode="after")
    def valid_range(self):
        if self.end<self.start or self.maximum<self.minimum:raise ValueError("Invalid range")
        if self.mode=="partial" and not self.factors:raise ValueError("Choose at least one factor")
        if self.mode in ("sign","nakshatra","sub","longitude") and not self.planets:raise ValueError("Choose at least one planet")
        return self
class Generation(BaseModel):
    start:date
    end:date
    clock:str="10:30"
    step:Literal[0,1,5,15,30]=0
class Feedback(BaseModel):
    page:str=Field(max_length=100)
    timestamp:str=Field(max_length=100)
    result:str=Field("",max_length=500)
    expected:str=Field(min_length=1,max_length=1800)
    actual:str=Field(min_length=1,max_length=1800)
    comments:str=Field("",max_length=1800)

@app.get("/api/health")
def health():return {"status":"ok","model":MODEL,"now":datetime.now(IST).isoformat(),"profile":{"lat":LAT,"lon":LON,"ayanamsa":"Lahiri","houses":"Placidus","node":"Mean"}}
@app.get("/api/coverage")
def coverage():
    with LOCK,db() as con:
        return {"daily":clean(con.sql("select instrument,count(*) records,min(day) earliest,max(day) latest from daily group by 1").df()),
        "intraday":clean(con.sql("select source,count(*) records,min(timestamp) earliest,max(timestamp) latest from intraday group by 1").df()),
        "features":con.execute("select count(*) from snapshots where model=?",[MODEL]).fetchall()[0][0],
        "audit":clean(con.sql("select status,count(*) sessions from minute_audit group by 1").df()),
        "missing_sessions":con.sql("select count(*) from trading_dates where day between (select min(timestamp)::date from intraday) and (select max(timestamp)::date from intraday) and day not in (select distinct timestamp::date from intraday)").fetchall()[0][0],
        "incomplete_dates":con.sql("select count(*) from (select timestamp::date,count(*) n from intraday group by 1 having n<375)").fetchall()[0][0],
        "sources":clean(con.sql("select provider,count(*) records from daily group by 1").df()),
        "last_sync":str(con.sql("select max(imported_at) from intraday").fetchall()[0][0])}
@app.post("/api/calculate",response_model=CalculationResponse)
def calculate(body:Moment):
    with LOCK:
        chart=KPChart(body.timestamp)
        result=json.loads(detailed(body.timestamp))
    signs=["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    names="Ashwini Bharani Krittika Rohini Mrigashira Ardra Punarvasu Pushya Ashlesha Magha Purva-Phalguni Uttara-Phalguni Hasta Chitra Swati Vishakha Anuradha Jyeshtha Mula Purva-Ashadha Uttara-Ashadha Shravana Dhanishta Shatabhisha Purva-Bhadrapada Uttara-Bhadrapada Revati".split()
    result["rows"]=[dict(planet=p,**v,zodiac=signs[int(v["longitude"]/30)],nakshatra_name=names[v["nakshatra"]-1]) for p,v in result["positions"].items()]
    return result
def search_rows(con,body,all_rows=False):
    selected=KPChart(body.timestamp)
    kp=selected.calculate()
    clauses=["model=?","lat=?","lon=?","ts<?","ts::DATE BETWEEN ? AND ?"]
    args=[MODEL,LAT,LON,body.timestamp,body.start,body.end]
    for k in (FACTORS if body.mode=="exact" else body.factors if body.mode=="partial" else []):
        clauses.append(f"json_extract_string(details,'$.ruling_planets.{k}')=?")
        args.append(kp["ruling_planets"][k])
    if body.mode=="score":
        clauses.append("CAST(json_extract(details,'$.kp_score') AS DOUBLE) BETWEEN ? AND ?")
        args.extend([body.minimum,body.maximum])
    for p in body.planets if body.mode in ("sign","nakshatra","sub","longitude") else []:
        expr=f"CAST(json_extract(details,'$.positions.{p}.longitude') AS DOUBLE)"
        x=selected.longitude(p)
        if body.mode=="sign":clauses.append(f"floor({expr}/30)=?");args.append(int(x/30))
        elif body.mode=="nakshatra":clauses.append(f"floor({expr}/(360.0/27))=?");args.append(int(x/(360/27)))
        elif body.mode=="sub":clauses.append(f"json_extract_string(details,'$.positions.{p}.sub')=?");args.append(sub_lord(x))
        else:clauses.append(f"abs((({expr}-?+540)%360)-180)<=?");args.extend([x,body.tolerance])
    where=" AND ".join(clauses)
    count=con.execute("SELECT count(*) FROM snapshots WHERE "+where,args).fetchall()[0][0]
    suffix=" ORDER BY ts DESC" if all_rows else " ORDER BY ts DESC LIMIT ? OFFSET ?"
    rows=con.execute("SELECT ts AS timestamp,details FROM snapshots WHERE "+where+suffix,args if all_rows else args+[body.limit,body.offset]).df()
    return count,rows,kp
@app.post("/api/matches",response_model=MatchResponse)
def matches(body:Search):
    with LOCK,db() as con:
        count,rows,kp=search_rows(con,body)
        records=[]
        for r in rows.itertuples():
            detail=json.loads(r.details)
            records.append(dict(timestamp=r.timestamp,score=detail["kp_score"],**detail["ruling_planets"],
                matched=sum(detail["ruling_planets"][k]==kp["ruling_planets"][k] for k in FACTORS),
                differences=", ".join(k for k in FACTORS if detail["ruling_planets"][k]!=kp["ruling_planets"][k]),category=body.mode,
                matched_factors=", ".join(k for k in FACTORS if detail["ruling_planets"][k]==kp["ruling_planets"][k])))
        frame=pd.DataFrame(records)
        if len(frame):
            for h in [5,15,30,60]:
                out=attach_prices(con,frame[["timestamp"]],h)
                frame["reference"]=out.close
                frame[f"price_{h}"]=out.exit_price
                frame[f"points_{h}"]=out.exit_price-out.close
                frame[f"return_{h}"]=100*(out.exit_price/out.close-1)
            metadata=con.execute("SELECT timestamp,source,quality,interval_minutes FROM intraday WHERE timestamp IN (SELECT timestamp FROM frame)").df()
            frame=frame.merge(metadata,on="timestamp",how="left")
            frame["market_data"]=frame["reference"].notna().map({True:"Available",False:"Intraday NIFTY data unavailable for this date."})
        return {"total":count,"rows":clean(frame)}

@app.post("/api/statistics")
def statistics(body:Search):
    with LOCK,db() as con:
        count,rows,_=search_rows(con,body,True)
        if rows.empty:return {"matches":0,"with_data":0,"without_data":0}
        out=attach_prices(con,rows[["timestamp"]],body.horizon)
    values=(100*(out.exit_price/out.close-1)).dropna()
    points=(out.exit_price-out.close).dropna()
    present=int(out.close.notna().sum())
    return {"matches":count,"with_data":present,"without_data":count-present,"complete_forward_windows":len(values),
        "incomplete_forward_windows":present-len(values),
        "positive":int((values>0).sum()),"negative":int((values<0).sum()),"flat":int((values==0).sum()),
        "average_points":float(points.mean()) if len(points) else None,
        "median_points":float(points.median()) if len(points) else None,
        "average_percent":float(values.mean()) if len(values) else None,
        "observed_positive_frequency":float((values>0).mean()) if len(values) else None}
@app.get("/api/candles",response_model=CandleResponse)
def candles(timestamp:datetime,interval:int=1):
    if interval not in (1,5,15):raise HTTPException(422,"Unsupported candle interval")
    if timestamp.tzinfo is None:raise HTTPException(422,"Timezone required")
    t=pd.Timestamp(timestamp).tz_convert(IST)
    with LOCK,db() as con:
        rows=con.execute("SELECT timestamp,open,high,low,close FROM intraday WHERE timestamp::DATE=? AND interval_minutes=1 AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL ORDER BY timestamp",[t.date()]).df()
    if interval>1 and len(rows):
        rows=rows.set_index("timestamp")
        group=rows.resample(f"{interval}min",origin=rows.index[0]-pd.Timedelta(minutes=1),closed="right",label="right")
        grouped=group.agg({"open":"first","high":"max","low":"min","close":"last"})
        rows=grouped[group.close.count()==interval].reset_index()
    return {"rows":clean(rows),"convention":"Candle-close timestamps. Forward returns are descriptive observed index changes."}
@app.get("/api/studies")
def studies():
    from private_demo.install_connector import HOME
    result={}
    for name in ["daily_walk_forward","intraday_holdout"]:
        frame=pd.read_csv(ROOT/"archive"/"reports"/(name+".csv"))
        result[name]={"rows":len(frame),"accuracy":float((frame.prediction==frame["actual" if name.startswith("daily") else "outcome"]).mean()),
            "baseline":float((frame.baseline==frame["actual" if name.startswith("daily") else "outcome"]).mean())}
    return result
@app.get("/api/upstox")
def broker_status():return {"configured":bool(token()),"instrument":"NSE_INDEX|Nifty 50"}
@app.post("/api/admin/upstox/test")
def broker_test():
    from upstox_history import verify_instrument,fetch
    secret=token()
    if not secret:raise HTTPException(409,"Configure the token with configure_upstox.bat.")
    try:
        instrument=verify_instrument()
        today=datetime.now(IST).date()
        result=fetch(secret,today,today,True)
        return {"instrument":instrument["instrument_key"],"received":len(result["data"]["candles"])}
    except Exception:raise HTTPException(502,"Upstox rejected the request or is unavailable. Check token validity.")
def job(work):
    key=uuid.uuid4().hex
    JOBS[key]={"status":"queued","done":0,"cancel":False}
    save_jobs()
    def run():
        JOBS[key]["status"]="running"
        try:
            progress_iter=iter(work())
            while not JOBS[key]["cancel"]:
                try:progress=next(progress_iter)
                except StopIteration:break
                JOBS[key]["done"]=str(progress)
                save_jobs()
            if hasattr(progress_iter,"close"):progress_iter.close()
            JOBS[key]["status"]="cancelled" if JOBS[key]["cancel"] else "complete"
        except Exception:JOBS[key]["status"]="failed";JOBS[key]["error"]="Operation failed. Check range, credentials and provider availability."
        finally:save_jobs()
    POOL.submit(run)
    return {"id":key}
@app.post("/api/admin/features")
def features(body:Generation):
    if body.end<body.start or (body.end-body.start).days>3660:raise HTTPException(422,"Use a range up to ten years per job.")
    try:time_value=clock.fromisoformat(body.clock)
    except ValueError:raise HTTPException(422,"Invalid clock time")
    def run():
        for day in pd.date_range(body.start,body.end):
            times=[pd.Timestamp.combine(day,time_value).tz_localize(IST)] if body.step==0 else pd.date_range(day+pd.Timedelta(hours=9,minutes=15),day+pd.Timedelta(hours=15,minutes=30),freq=f"{body.step}min",tz=IST)
            with LOCK,db(write=True) as con:list(build(con,times))
            yield str(day.date())
    return job(run)
@app.post("/api/admin/sync")
def synchronize(body:Generation):
    from upstox_history import sync_minutes
    if not token():raise HTTPException(409,"Configure the token locally first.")
    if body.end<body.start:raise HTTPException(422,"Invalid date range")
    def run():
        # The existing adapter owns its transactions. One worker serializes sync jobs.
        yield from sync_minutes(token(),body.start,body.end,None)
    return job(run)
@app.get("/api/admin/jobs")
def jobs():return JOBS

@app.post("/api/admin/sync-daily")
def synchronize_daily(body:Generation):
    from upstox_daily import sync_daily
    if not token():raise HTTPException(409,"Configure the token locally first.")
    if body.end<body.start:raise HTTPException(422,"Invalid range")
    return job(lambda:sync_daily(token(),body.start,body.end))
@app.post("/api/admin/jobs/{key}/cancel")
def cancel(key:str):
    if key not in JOBS:raise HTTPException(404)
    JOBS[key]["cancel"]=True
    return {"status":"cancellation requested"}
@app.post("/api/feedback")
def feedback(body:Feedback):
    import sqlite3
    from datetime import timezone
    from contextlib import closing
    from private_demo.install_connector import HOME
    HOME.mkdir(exist_ok=True)
    with closing(sqlite3.connect(HOME/"custom-feedback.sqlite3")) as con,con:
        con.execute("CREATE TABLE IF NOT EXISTS feedback(created TEXT,feature TEXT,expected TEXT,actual TEXT,comments TEXT)")
        con.execute("INSERT INTO feedback VALUES(?,?,?,?,?)",[datetime.now(timezone.utc).isoformat(),body.page,body.expected,body.actual,json.dumps(body.model_dump(exclude={"expected","actual"}))])
    return {"saved":True}
@app.get("/api/admin/feedback")
def feedback_review():
    import sqlite3
    from contextlib import closing
    from private_demo.install_connector import HOME
    path=HOME/"custom-feedback.sqlite3"
    if not path.exists():return []
    with closing(sqlite3.connect(path)) as con:return clean(pd.read_sql_query("SELECT * FROM feedback ORDER BY rowid DESC",con))
app.mount("/assets",StaticFiles(directory=ROOT/"web/dist/assets",check_dir=False),name="assets")
@app.get("/demo")
@app.get("/")
def index():return FileResponse(ROOT/"web/dist/index.html")


class Study(BaseModel):
    start:date=date(2026,9,1)
    end:date=date(2026,11,19)
    split:date=date(2026,11,1)
    horizon:int=Field(15,ge=1,le=60)
    minimum:int=Field(5,ge=1,le=1000)
    cost:float=Field(2,ge=0,le=1000)
    mode:Literal["daily","intraday"]="intraday"
    key:Literal["score","majority","moon_star","moon_sub","lagna"]="score"

@app.post("/api/backtest")
def run_study(body:Study):
    from custom_services import backtest
    if body.end<body.start or (body.end-body.start).days>366 and body.mode=="intraday":
        raise HTTPException(422,"Intraday studies are limited to one year per request.")
    with LOCK,db() as con:
        rows=backtest(con,body.start,body.end,body.split,body.horizon,body.minimum,body.cost,body.mode,body.key)
    if rows.empty:return {"rows":[],"n":0}
    observed=rows["actual"] if body.mode=="daily" else rows["outcome"]
    return {"rows":clean(rows),"n":len(rows),"accuracy":float((rows.prediction==observed).mean()),"baseline":float((rows.baseline==observed).mean())}

@app.get("/api/timeline")
def timeline(day:date,step:int=15):
    if step not in (1,5,15,30):raise HTTPException(422,"Unsupported sampling interval")
    from research import feature
    from kp_engine import slots
    with LOCK:
        rows=pd.DataFrame([feature(t) for t in slots(day,step)])
    return clean(rows)

class Lab(BaseModel):
    first:int=Field(2016,ge=1997,le=2100)
    minimum:int=Field(20,ge=1,le=1000)

@app.post("/api/admin/lab")
def laboratory(body:Lab):
    from custom_services import factor_lab
    with LOCK,db() as con:return factor_lab(con,body.first,body.minimum)

@app.get("/api/admin/diagnostics")
def diagnostics():
    import subprocess,sys
    completed=subprocess.run([sys.executable,"-m","pytest","-q","tests/test_engine.py","tests/test_research.py","tests/test_archive.py"],cwd=ROOT,capture_output=True,text=True,timeout=60)
    return {"passed":completed.returncode==0,"output":completed.stdout[-5000:]}

class CsvImport(BaseModel):
    csv:str=Field(max_length=10000000)
    source:str=Field(min_length=1,max_length=120)
    timezone:str="Asia/Kolkata"
    interval:int=Field(1,ge=1,le=60)
    start_labels:bool=True

@app.post("/api/admin/import")
def import_prices(body:CsvImport):
    import io,hashlib
    from research import prepare
    from minute_archive import store_bars
    from historical import RAW
    data=pd.read_csv(io.StringIO(body.csv))
    if not {"timestamp","close"}.issubset(data):raise HTTPException(422,"CSV requires timestamp and close, with optional open/high/low.")
    cols=[c for c in ["timestamp","open","high","low","close"] if c in data]
    bars=prepare(data,{c:c for c in cols},body.timezone,body.interval,body.start_labels,True)
    raw=body.csv.encode()
    path=RAW/("custom-import-"+hashlib.sha256(raw).hexdigest()+".csv")
    path.write_bytes(raw)
    with LOCK,db(write=True) as con:store_bars(con,bars,body.source,str(path),"User supplied","start" if body.start_labels else "close",body.interval)
    return {"imported":len(bars)}
