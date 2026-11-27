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
app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv("NIFTY_ALLOWED_HOSTS","127.0.0.1,localhost,testserver").split(","))
def db(write=False):
    con=duckdb.connect(str(DB))
    con.execute("SET TimeZone='Asia/Kolkata'")
    if os.getenv("NIFTY_CLOUD")=="1":
        con.execute("SET memory_limit='128MB'")
        con.execute("SET threads=1")
    if not write:con.execute("BEGIN TRANSACTION READ ONLY")
    return con
def clean(df):return json.loads(df.to_json(orient="records",date_format="iso"))
def token():
    if os.getenv("NIFTY_CLOUD")=="1":return os.getenv("UPSTOX_ACCESS_TOKEN")
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
    mode:Literal["exact","exact_score","partial","sign","nakshatra","pada","star","sub","score","longitude","similarity"]="exact"
    similarity:float=Field(80,ge=0,le=100)
    weights:list[float]=Field(default_factory=lambda:[1,1,1,1,1],min_length=5,max_length=5)
    factors:list[Literal["day","moon_sign","moon_star","moon_sub","lagna","kp_score"]]=FACTORS
    planets:list[Literal["Sun","Moon","Mars","Mercury","Venus","Jupiter","Saturn","Rahu","Ketu"]]=["Moon"]
    tolerance:float=Field(5,ge=0,le=180)
    minimum:float=-30
    maximum:float=30
    offset:int=Field(0,ge=0)
    limit:int=Field(25,ge=1,le=100)
    horizon:Literal[5,15,30,60,120,240]=15
    completed_before:bool=False
    history_scope:Literal["astronomical","market"]="astronomical"
    neutral:float=Field(0,ge=0,le=10)
    @model_validator(mode="after")
    def valid_range(self):
        if any(w<0 for w in self.weights) or sum(self.weights)<=0:raise ValueError("Weights must be nonnegative with positive sum")
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
    result["rows"]=[dict(planet=p,**v,zodiac=signs[int(v["longitude"]/30)],nakshatra_name=names[v["nakshatra"]-1],pada=int((v["longitude"]%(360/27))/(360/108))+1) for p,v in result["positions"].items()]
    from kp_diagnostics import subdivision
    result['weekday']=body.timestamp.strftime('%A')
    result['day_lord_rule']='Gregorian weekday at local midnight in Asia/Kolkata; not sunrise vara, Hora or Rahu Kaal'
    result['moon_subdivision']=subdivision(chart.longitude('Moon'))
    result['model']=MODEL
    return result
def search_rows(con,body,all_rows=False):
    selected=KPChart(body.timestamp)
    kp=selected.calculate()
    clauses=["model=?","lat=?","lon=?","ts<?","ts::DATE BETWEEN ? AND ?"]
    args=[MODEL,LAT,LON,body.timestamp,body.start,body.end]
    if body.completed_before:
        clauses.append("ts+?*INTERVAL '1 minute'<=?")
        args.extend([body.horizon,body.timestamp])
    if body.history_scope=="market":
        clauses.append("EXISTS (SELECT 1 FROM intraday market WHERE market.timestamp=snapshots.ts AND market.interval_minutes=1)")
    for k in (FACTORS if body.mode in ("exact","exact_score") else body.factors if body.mode=="partial" else []):
        if k=="kp_score":continue
        clauses.append(f"json_extract_string(details,'$.ruling_planets.{k}')=?")
        args.append(kp["ruling_planets"][k])
    if body.mode=="exact_score" or (body.mode=="partial" and "kp_score" in body.factors):
        clauses.append("CAST(json_extract(details,'$.kp_score') AS DOUBLE)=?")
        args.append(kp['kp_score'])
    if body.mode=="score":
        clauses.append("CAST(json_extract(details,'$.kp_score') AS DOUBLE) BETWEEN ? AND ?")
        args.extend([body.minimum,body.maximum])
    if body.mode=="similarity":
        terms=[]
        for k,w in zip(FACTORS,body.weights):
            terms.append("CASE WHEN json_extract_string(details,'$.ruling_planets."+k+"')=? THEN ? ELSE 0 END")
            args.extend([kp['ruling_planets'][k],w])
        clauses.append("("+"+".join(terms)+")>=?")
        args.append(sum(body.weights)*body.similarity/100)
    for p in body.planets if body.mode in ("sign","nakshatra","pada","star","sub","longitude") else []:
        expr=f"CAST(json_extract(details,'$.positions.{p}.longitude') AS DOUBLE)"
        x=selected.longitude(p)
        if body.mode=="sign":clauses.append(f"floor({expr}/30)=?");args.append(int(x/30))
        elif body.mode=="nakshatra":clauses.append(f"floor({expr}/(360.0/27))=?");args.append(int(x/(360/27)))
        elif body.mode=="pada":clauses.append(f"floor({expr}/(360.0/108))=?");args.append(int(x/(360/108)))
        elif body.mode=="star":clauses.append(f"json_extract_string(details,'$.positions.{p}.star')=?");args.append(star_lord(x))
        elif body.mode=="sub":clauses.append(f"json_extract_string(details,'$.positions.{p}.sub')=?");args.append(sub_lord(x))
        else:clauses.append(f"abs((({expr}-?+540)%360)-180)<=?");args.extend([x,body.tolerance])
    where=" AND ".join(clauses)
    count=con.execute("SELECT count(*) FROM snapshots WHERE "+where,args).fetchall()[0][0]
    suffix=" ORDER BY ts DESC" if all_rows else " ORDER BY ts DESC LIMIT ? OFFSET ?"
    projection="ts AS timestamp" if all_rows else "ts AS timestamp,details"
    rows=con.execute("SELECT "+projection+" FROM snapshots WHERE "+where+suffix,args if all_rows else args+[body.limit,body.offset]).df()
    return count,rows,kp
@app.post("/api/matches",response_model=MatchResponse)
def matches(body:Search):
    with LOCK,db() as con:
        count,rows,kp=search_rows(con,body)
        records=[]
        for r in rows.itertuples():
            detail=json.loads(r.details)
            required=body.factors if body.mode=="partial" else [*FACTORS,"kp_score"] if body.mode=="exact_score" else FACTORS if body.mode=="exact" else []
            agrees=lambda k: detail['kp_score']==kp['kp_score'] if k=='kp_score' else detail['ruling_planets'][k]==kp['ruling_planets'][k]
            records.append(dict(timestamp=r.timestamp,score=detail["kp_score"],**detail["ruling_planets"],required_factors=", ".join(required),required_matched=sum(agrees(k) for k in required),required_total=len(required),
                matched=sum(detail["ruling_planets"][k]==kp["ruling_planets"][k] for k in FACTORS)+(int(detail["kp_score"]==kp["kp_score"]) if body.mode=="exact_score" else 0),
                differences=", ".join(k for k in FACTORS if detail["ruling_planets"][k]!=kp["ruling_planets"][k]),category=body.mode,similarity=100*sum(w for k,w in zip(FACTORS,body.weights) if detail["ruling_planets"][k]==kp["ruling_planets"][k])/sum(body.weights) if body.mode=="similarity" else None,
                matched_factors=", ".join([k for k in (body.factors if body.mode=="partial" else FACTORS) if k!="kp_score" and detail["ruling_planets"][k]==kp["ruling_planets"][k]]+(["kp_score"] if (body.mode=="exact_score" or body.mode=="partial" and "kp_score" in body.factors) and detail["kp_score"]==kp["kp_score"] else []))))
        frame=pd.DataFrame(records)
        if len(frame):
            for h in [5,15,30,60,120,240]:
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
        "positive":int((values>body.neutral).sum()),"negative":int((values < -body.neutral).sum()),"flat":int((values.abs()<=body.neutral).sum()),
        "positive_percent":float(100*(values>body.neutral).mean()) if len(values) else None,
        "negative_percent":float(100*(values < -body.neutral).mean()) if len(values) else None,
        "neutral_percent":float(100*(values.abs()<=body.neutral).mean()) if len(values) else None,
        "neutral_threshold_percent":body.neutral,
        "median_percent":float(values.median()) if len(values) else None,
        "average_positive_points":float(points[values>body.neutral].mean()) if (values>body.neutral).any() else None,
        "average_negative_points":float(points[values < -body.neutral].mean()) if (values < -body.neutral).any() else None,
        "median_positive_points":float(points[values>body.neutral].median()) if (values>body.neutral).any() else None,
        "median_negative_points":float(points[values < -body.neutral].median()) if (values < -body.neutral).any() else None,
        "largest_positive_points":float(points.max()) if len(points) and points.max()>0 else None,
        "largest_negative_points":float(points.min()) if len(points) and points.min()<0 else None,
        "average_points":float(points.mean()) if len(points) else None,
        "median_points":float(points.median()) if len(points) else None,
        "average_percent":float(values.mean()) if len(values) else None,
        "observed_positive_frequency":float((values>body.neutral).mean()) if len(values) else None}
@app.get('/api/kp/slot-matches')
def exact_slot_matches(timestamp:datetime,offset:int=0,limit:int=25):
    if timestamp.tzinfo is None:raise HTTPException(422,'Timezone required')
    if offset<0 or not 1<=limit<=100:raise HTTPException(422,'Invalid pagination')
    from full_day_archive import slot_search
    with LOCK:
        result=slot_search(timestamp)
        page=result['rows'][offset:offset+limit]
        with db() as con:
            for row in page:
                t=datetime.fromisoformat(row['timestamp']);end=t+timedelta(minutes=15)
                fresh=KPChart(t).calculate()
                for archive_key,engine_key in zip(['day_lord','moon_sign_lord','moon_star_lord','moon_sub_lord','lagna_lord'],FACTORS):
                    if row.get(archive_key)!=fresh['ruling_planets'][engine_key]:raise HTTPException(409,'Historical slot failed fresh KP verification; archive requires rebuilding')
                if row.get('kp_score')!=fresh['kp_score']:raise HTTPException(409,'Historical score failed fresh KP verification; archive requires rebuilding')
                row['verification']='Recalculated: 6/6 agree'

                bars=con.execute('SELECT timestamp,open,close FROM intraday WHERE timestamp>? AND timestamp<=? AND timestamp::DATE=? AND interval_minutes=1 ORDER BY timestamp',[t,end,t.date()]).fetchall()
                complete=len(bars)==15 and all(b[0]==t+timedelta(minutes=i+1) and b[1] is not None and b[2] is not None for i,b in enumerate(bars))
                row.update(slot_end=end.isoformat(),minute_candles=len(bars),market_data='Complete' if complete else 'Incomplete' if bars else 'Unavailable',slot_open=float(bars[0][1]) if complete else None,slot_close=float(bars[-1][2]) if complete else None)
        result.update(rows=page,offset=offset,limit=limit)
    return result

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

@app.get("/api/market")
def market():
    from market_status import status
    return status(token())

@app.get('/api/ml/evaluation')
def ml_evaluation():
    from ml_research import OUT
    if not (OUT/'metrics.json').exists():return {'status':'unavailable','metrics':[],'predictions':[]}
    frame=pd.read_parquet(OUT/'predictions.parquet')
    return {'status':'historical replay only','metrics':json.loads((OUT/'metrics.json').read_text()),'predictions':clean(frame.tail(500)),'calibration':json.loads((OUT/'calibration.json').read_text()) if (OUT/'calibration.json').exists() else []}

@app.get('/api/ml/movement')
def movement_evaluation(day:date|None=None,target:str|None=None,model_name:str|None=None):
    from movement_models import OUT
    if not (OUT/'metrics.json').exists():return {'metrics':[],'predictions':[],'status':'Prediction unavailable'}
    frame=pd.read_parquet(OUT/'predictions.parquet')
    if day is not None:frame=frame[pd.to_datetime(frame.timestamp,utc=True).dt.tz_convert(IST).dt.date==day]
    if target is not None:frame=frame[frame.target==target]
    if model_name is not None:frame=frame[frame.model==model_name]
    return {'metrics':json.loads((OUT/'metrics.json').read_text()),'predictions':clean(frame.tail(500)),'status':'Development replay only; 2026 excluded'}

@app.get('/api/trajectory-metrics')
def trajectory_metrics():
    path=ROOT/'archive/trajectory/metrics.json'
    return {'rows':json.loads(path.read_text()) if path.exists() else []}

@app.get('/api/historical-forecast')
def historical_forecast(timestamp:datetime,model:Literal['baseline','market','kp','combined','analog']='market',horizon:int=60):
    from historical_forecast import forecast
    if horizon not in (15,30,60,120,240):raise HTTPException(422,'Endpoint overlay supports elapsed horizons only')
    with LOCK:return json.loads(json.dumps(forecast(timestamp,model,horizon),default=lambda v:v.item() if isinstance(v,np.generic) else str(v)))

@app.get('/api/admin/paper')
def paper_status():
    from paper_service import status
    from paper_scheduler import config
    from quarantine import status as quarantine_status
    return {**status(),'schedule':config(),'quarantine':quarantine_status(),'operational_states':['HISTORICAL_REPLAY','QUARANTINED_PROSPECTIVE','APPROVED_PAPER','BLOCKED']}

@app.post('/api/admin/paper/quarantine/collect')
def collect_quarantine():
    from paper_service import registry
    from market_status import status
    from quarantine import collect
    models=registry()
    if not models:raise HTTPException(409,'No registered model')
    observation=status(token())['rows'][0]
    try:key=collect(models[0],observation,datetime.now(IST).strftime('%H:%M'))
    except (ValueError,TypeError,KeyError) as exc:raise HTTPException(409,str(exc))
    return {'state':'QUARANTINED_PROSPECTIVE','id':key}

class PaperSchedule(BaseModel):
    enabled:bool=False
    quarantine_enabled:bool=False
    quarantine_model_ids:list[str]=Field(default_factory=list,max_length=96)
    windows:list[str]=Field(default_factory=lambda:['09:30','10:00','11:00','12:00','13:00','14:00'],max_length=20)

@app.post('/api/admin/paper/schedule')
def paper_schedule(body:PaperSchedule):
    from bundle_runtime import models
    known={m['runtime_id'] for m in models()}
    if any(v not in known for v in body.quarantine_model_ids):raise HTTPException(422,'Unknown registered model ID')
    from paper_scheduler import save,config
    for v in body.windows:
        try:clock.fromisoformat(v)
        except ValueError:raise HTTPException(422,'Invalid IST time')
    save({**config(),**body.model_dump()})
    return config()

@app.on_event('startup')
def start_paper_worker():
    if os.getenv("NIFTY_CLOUD")=="1":return
    from paper_scheduler import start
    start()

@app.on_event('shutdown')
def stop_paper_worker():
    from paper_scheduler import STOP
    STOP.set()

@app.post('/api/admin/paper/settle')
def paper_settle():
    from paper_service import settle,status
    with LOCK,db() as con:settle(con)
    return status()

@app.get('/api/daily-research')
def daily_research(day:date):
    with LOCK,db() as con:
        bars=con.execute('select timestamp,open,high,low,close from intraday where timestamp::date=? order by timestamp',[day]).df()
        features=con.execute('select ts timestamp,details from snapshots where ts::date=? and model=? order by ts',[day,MODEL]).df()
    from kp_engine import slots
    transitions=[];previous=None;timeline=[]
    with LOCK:
        for stamp in slots(day):
            d=KPChart(stamp).calculate()
            item={'timestamp':stamp,'score':d['kp_score'],**d['ruling_planets'],**d['components']}
            timeline.append(item)
            state=(d['kp_score'],d['signature'])
            if state!=previous:transitions.append(item);previous=state
    from paper_service import status as paper_records
    forecasts=[r for r in paper_records()['predictions'] if r['kind']=='prospective paper' and pd.Timestamp(r['timestamp']).tz_convert(IST).date()==day]
    return {'timeline':clean(pd.DataFrame(timeline)),'predictions':forecasts,'candles':clean(bars),'transitions':clean(pd.DataFrame(transitions)),'model':MODEL,'coverage':'KP timeline calculated for selected date independently of market-data availability; 15-minute samples, not exact transition instants'}

@app.get('/api/kp/full-day-matches')
def full_day_matches(day:date):
    from full_day_archive import search
    with LOCK:return search(day)

@app.on_event('startup')
def update_full_day_archive():
    if os.getenv("NIFTY_CLOUD")=="1":return  # Snapshot updates are published explicitly.
    import subprocess,sys
    subprocess.Popen([sys.executable,'-m','full_day_archive'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)

@app.post('/api/admin/kp/full-day-refresh')
def refresh_full_day_archive():
    update_full_day_archive()
    return {'status':'catch-up requested; existing worker is preserved'}
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

@app.post("/api/admin/index-market")
def index_market(body:Generation):
    if body.end<body.start:raise HTTPException(422,'Invalid range')
    def run():
        with LOCK,db() as con:
            times=con.execute("select timestamp from intraday where interval_minutes=1 and timestamp::date between ? and ? order by timestamp",[body.start,body.end]).df().timestamp
        stride=body.step or 15
        times=times[(times.dt.hour*60+times.dt.minute)%stride==0]
        for i in range(0,len(times),128):
            with LOCK,db(write=True) as con:list(build(con,times.iloc[i:i+128]))
            yield {'processed':min(i+128,len(times)),'eligible':len(times),'model':MODEL}
    return job(run)

@app.post("/api/research/outcomes")
def longer_outcomes(body:Search,outcome:Literal['elapsed','remainder','next_session','next_day_close']='elapsed'):
    from market_research import outcomes
    with LOCK,db() as con:
        count,rows,_=search_rows(con,body)
        if rows.empty:return {'total':count,'rows':[]}
        frame=outcomes(con,rows[['timestamp']],outcome,body.horizon)
    frame['points']=frame.exit_price-frame.close
    frame['return_percent']=100*(frame.exit_price/frame.close-1)
    return {'total':count,'definition':outcome,'minutes':body.horizon,'rows':clean(frame)}

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
    if os.getenv("NIFTY_CLOUD")=="1":
        from cloud_firebase import save_feedback
        return save_feedback(body.model_dump())
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
