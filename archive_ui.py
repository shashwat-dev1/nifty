"""Historical workspaces for the local Streamlit terminal."""
from datetime import date,time,timedelta
from itertools import combinations
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from historical import connect,build,cached,daily_outcomes,walk_forward,sync,ROOT,MODEL,IST
from kp_engine import PLANETS,KPChart
from research import FACTORS,DB as INTRADAY
from upstox_history import KEY,verify_instrument,fetch,sync_minutes

def table(df,name):
    st.dataframe(df,width="stretch",hide_index=True)
    st.download_button("Export "+name,df.to_csv(index=False),name+".csv","text/csv")

def prices(db):
    return db.sql("SELECT * FROM daily WHERE instrument='NIFTY 50' ORDER BY day").df()

def coverage(db):
    return db.sql("SELECT instrument,count(*) AS records,min(day) AS earliest,max(day) AS latest,max(imported_at) AS imported FROM daily GROUP BY 1 ORDER BY 1").df()

def calculate(db,times,lat,lon):
    bar=st.progress(0,text="Checking saved configurations")
    for done,total in build(db,times,lat,lon):
        bar.progress(done/total,text=f"Saved {done:,} of {total:,} new configurations")
    bar.empty()

def joined_daily(db,frame,h,lat,lon):
    values=daily_outcomes(frame,h)
    feat=cached(db,frame.day.min(),frame.day.max(),lat,lon,time(0))
    feat["day_key"]=feat.timestamp.dt.date
    values["day_key"]=values.day.dt.date
    # day is also the engine name for weekday lord.
    return values.merge(feat.rename(columns={"day":"day_lord"}),on="day_key",how="inner")

def health(db,bars):
    st.subheader("Historical coverage")
    st.dataframe(coverage(db),hide_index=True)
    st.dataframe(db.sql("SELECT source,count(*) AS candles,min(timestamp) AS earliest,max(timestamp) AS latest FROM intraday GROUP BY source").df())
    st.dataframe(db.sql("SELECT year(day) AS year,status,count(*) AS sessions,sum(bars) AS candles FROM minute_audit GROUP BY ALL ORDER BY 1,2").df())
    st.caption("Minute archive uses start-labelled, timezone-checked candles. Sessions must reconcile against both NSE daily extremes within 0.10 index points. A session-level check cannot independently certify every tick.")
    st.caption("Daily dates are IST session labels. Index levels have no traded volume. Equal or invalid OHLC ranges retain only the valid close. Pre-launch observations are flagged.")
    yearly=db.sql("SELECT year(day) AS year,instrument,count(*) AS observations FROM daily GROUP BY ALL ORDER BY 1").df()
    st.plotly_chart(px.bar(yearly,x="year",y="observations",color="instrument",barmode="group"))
    table(yearly,"yearly_coverage")
    frame=prices(db)
    if len(frame):
        missing=pd.bdate_range(frame.day.min(),frame.day.max()).difference(frame.day)
        with st.expander("Weekdays without daily observations"):
            st.caption("Includes holidays. An official historical calendar is needed to distinguish a missing session.")
            st.dataframe(pd.DataFrame({"weekday":missing}))
    st.write("Source records")
    st.dataframe(db.sql("SELECT provider,quality,count(*) AS rows FROM daily GROUP BY ALL").df())
    st.dataframe(db.sql("SELECT * FROM sync_log ORDER BY attempt DESC LIMIT 30").df())
    with st.expander("Import an official index CSV"):
        st.caption("Supports NSE index-close reports and Nifty Indices historical exports. The file must identify the spot index by name.")
        upload=st.file_uploader("Daily index report",type="csv",key="daily_upload")
        if upload and st.button("Import daily observations"):
            import hashlib
            from historical import insert_daily,parse_report,RAW
            data=pd.read_csv(upload)
            data.columns=data.columns.str.strip()
            data=data.rename(columns={"Date":"Index Date","Open":"Open Index Value","High":"High Index Value","Low":"Low Index Value","Close":"Closing Index Value"})
            if "Index Name" not in data or "Index Date" not in data:
                raise ValueError("Expected Index Name and Date columns")
            data["Index Date"]=pd.to_datetime(data["Index Date"],dayfirst=True,format="mixed").dt.strftime("%d-%m-%Y")
            dest=RAW/("user-daily-"+hashlib.sha256(upload.getvalue()).hexdigest()+".csv")
            dest.write_bytes(upload.getvalue())
            rows=[]
            for label,group in data.groupby("Index Date"):
                rows.extend(parse_report(group.to_csv(index=False).encode(),pd.to_datetime(label,format="%d-%m-%Y").date(),upload.name,str(dest.relative_to(ROOT))))
            if not rows:raise ValueError("No supported spot index names")
            insert_daily(db,rows)
            st.success(f"Validated {len(rows):,} daily records")
    with st.expander("Intraday session checks and source discrepancies"):
        table(db.sql("SELECT * FROM minute_audit ORDER BY day").df(),"minute_session_audit")
        st.dataframe(db.sql("SELECT * FROM broker_conflicts ORDER BY timestamp DESC LIMIT 500").df())
    st.subheader("Sync official daily reports")
    last=frame.day.max().date() if len(frame) else date.today()-timedelta(days=7)
    dates=st.date_input("NSE report dates",(last,date.today()),min_value=date(1995,1,1))
    if st.button("Download daily reports") and len(dates)==2:
        for day,status in sync(db,*dates):st.write(f"{day} · {status}")
        st.caption("Reopen coverage to view the updated totals. Build features for newly added dates in the archive workspace.")

def match_configurations(df,kp,chart,fields,majority=False,classes=(),components=(),limits=None,selected=(),tol=0):
    for k in fields:df=df[df[k]==kp["ruling_planets"][k]]
    if majority:df=df[df.majority==kp["majority"]]
    for k in classes:df=df[df[k+"_classification"]==kp["ruling_details"][FACTORS.index(k)]["class"]]
    for k in components:df=df[df[k]==kp["components"][k]]
    if limits is not None:df=df[df.score.between(*limits)]
    if selected:
        def dist(a,b):return abs((a-b+180)%360-180)
        for p in selected:df=df[dist(df[p],chart.longitude(p))<=tol]
        for p,q in combinations(selected,2):
            df=df[abs(dist(df[p],df[q])-dist(chart.longitude(p),chart.longitude(q)))<=tol]
    return df.copy()

def archive_search(db,ts,lat,lon,h,bars):
    frame=prices(db)
    mode=st.radio("Outcome source",["Intraday candles","Daily index sessions"],horizontal=True)
    daily=mode.startswith("Daily")
    decision=time(0) if daily else ts.time().replace(tzinfo=None)
    target=ts.normalize() if daily else ts
    chart=KPChart(target,lat,lon)
    kp=chart.calculate()
    st.caption(f"Query configuration · {target:%d %b %Y %H:%M IST} · {kp['signature']} · score {kp['kp_score']:g}")
    first=frame.day.min().date() if len(frame) else date(1995,11,3)
    dates=st.date_input("Search earlier dates",(first,max(first,ts.date()-timedelta(days=1))),min_value=date(1900,1,1))
    if len(dates)!=2:return
    end=min(dates[1],ts.date()-timedelta(days=1))
    if end<dates[0]:
        st.info("Select a chart date after the start of the search period.")
        return
    sampling=st.selectbox("Calculation times",["Selected clock time"] if daily else ["All saved times","Selected clock time","1-minute grid","5-minute grid","15-minute grid","30-minute grid"])
    with st.expander("Build or resume historical configurations"):
        source=st.radio("Dates to calculate",["Observed daily index dates","Every calendar date (astronomy only)"])
        days=frame.loc[frame.day.between(pd.Timestamp(dates[0]),pd.Timestamp(end)),"day"] if source.startswith("Observed") else pd.date_range(dates[0],end)
        if "grid" in sampling:
            st.caption("This is a user-defined IST observation grid. Trading status requires an observed price.")
            a,b=st.columns(2)
            start=a.time_input("Grid start",time(9,15))
            stop=b.time_input("Grid end",time(15,30))
            if start>stop:st.error("Grid end precedes start.");return
        if sampling=="All saved times":st.caption("New snapshots will use the selected chart clock time. Search includes all saved intraday times.")
        if st.button("Calculate and save range"):
            # Bounded batches allow a decades-long minute request to resume safely.
            by_year=pd.DatetimeIndex(days)
            for year in by_year.year.unique():
                selected=by_year[by_year.year==year]
                if "grid" not in sampling:
                    times=[pd.Timestamp.combine(d,decision).tz_localize(IST) for d in selected]
                else:
                    step=int(sampling.split("-")[0])
                    times=[t for d in selected for t in pd.date_range(pd.Timestamp.combine(d,start),pd.Timestamp.combine(d,stop),freq=f"{step}min",tz=IST)]
                calculate(db,times,lat,lon)
    search=st.selectbox("Match historical configurations",["Exact five lords","Partial signature","Score range","Angular similarity · experimental"])
    fields=FACTORS if search.startswith("Exact") else []
    if search.startswith("Partial"):fields=st.multiselect("Required lords",FACTORS,default=["moon_star"])
    if search.startswith("Score"): limits=st.slider("KP score range",-30,30,(int(kp["kp_score"]),int(kp["kp_score"])))
    if search.startswith("Angular"):
        selected=st.multiselect("Compare bodies",PLANETS,default=["Sun","Moon"])
        tol=st.slider("Maximum difference in degrees",0.1,180.,5.)
        if not selected:return
    majority=st.checkbox("Require same ruling majority")
    classes=st.multiselect("Require matching factor classifications",FACTORS)
    components=st.multiselect("Require equal component values",list(kp["components"]))
    sessions=st.selectbox("Forward daily sessions",[1,2,5,10,20]) if daily else None
    if not st.checkbox("Show matching observations",value=True):return
    df=cached(db,dates[0],end,lat,lon,decision if sampling=="Selected clock time" else None)
    if "grid" in sampling:
        mins=df.timestamp.dt.hour*60+df.timestamp.dt.minute
        begin=start.hour*60+start.minute
        df=df[mins.between(begin,stop.hour*60+stop.minute)&((mins-begin)%int(sampling.split("-")[0])==0)]
    if not daily and sampling=="All saved times":df=df[df.timestamp.dt.time!=time(0)].copy()
    all_times=df[["timestamp"]].copy()
    total=len(df)
    df=match_configurations(df,kp,chart,fields,majority,classes,components,
        limits if search.startswith("Score") else None,selected if search.startswith("Angular") else (),tol if search.startswith("Angular") else 0)
    if daily:
        observed=daily_outcomes(frame,sessions)
        observed=observed[observed.exit_day<pd.Timestamp(ts.date())]
        observed["session"]=observed.day.dt.date
        df["session"]=df.timestamp.dt.date
        df=df.merge(observed[["session","open","exit_price","return_pct"]],how="left",on="session")
    else:
        from minute_archive import attach_prices
        df=attach_prices(db,df,h)
        df["return_pct"]=100*(df.exit_price/df.close-1)
    df["era"]=np.where(df.timestamp.dt.date<date(1996,4,22),"Pre-launch","Published index era")
    df["outcome"]=np.sign(df.return_pct).map({1:"Up",0:"Flat",-1:"Down"}).fillna("Unavailable")
    st.write(f"{len(df):,} matches among {total:,} saved configurations · {df.return_pct.count():,} observed outcomes")
    if not total:st.info("Build configurations above for these dates, chart coordinates and clock time.")
    if df.return_pct.count():
        returns=df.return_pct.dropna()
        st.write(f"Observed upward frequency {(returns>0).mean():.1%} · Mean return {returns.mean():+.3f}%")
        sessions_hit=df[df.return_pct.notna()].assign(hit=lambda v:v.return_pct.gt(0)).groupby(lambda i:df.timestamp.loc[i].date()).hit.mean()
        if len(sessions_hit)>1:
            rng=np.random.default_rng(42)
            lo,hi=np.quantile([rng.choice(sessions_hit,len(sessions_hit)).mean() for _ in range(1000)],[.025,.975])
            st.caption(f"{len(sessions_hit)} distinct sessions · Equal-session up frequency {sessions_hit.mean():.1%} · 95% session bootstrap {lo:.1%} to {hi:.1%}.")
        if st.checkbox("Compare with all eligible saved observations"):
            if daily:
                base=observed[observed.session.isin(all_times.timestamp.dt.date)].return_pct.dropna()
            else:
                universe=attach_prices(db,all_times,h).dropna()
                base=100*(universe.exit_price/universe.close-1)
            if len(base):st.write(f"Unconditional up frequency {(base>0).mean():.1%} across {len(base):,} priced observations. Mean return {base.mean():+.3f}%.")
        if len(returns)<30:st.warning("Small sample. Frequency can change substantially with a few additional observations.")
    if df.outcome.isin(["Up","Down"]).any():
        with st.expander("Compare conditions in positive and negative matches"):
            st.caption("Exploratory summaries on the same matches. Test candidate factors on a separate period.")
            factor=st.selectbox("Compare factor",FACTORS+["majority","score"])
            st.dataframe(df[df.return_pct.notna()].groupby(factor).return_pct.agg(["size","median","mean"]))
    table(df,"archive_matches")
    if st.button("Save this match report locally"):
        from historical import save_report
        run=save_report(db,"matches",df,dict(model=MODEL,date=target.isoformat(),lat=lat,lon=lon,mode=mode,search=search,sampling=sampling,
            horizon=sessions if daily else h,start=str(dates[0]),end=str(end),required=fields,components=components,classes=classes,majority=majority,
            score_range=limits if search.startswith("Score") else None,bodies=selected if search.startswith("Angular") else [],tolerance=tol if search.startswith("Angular") else None))
        st.success(f"Saved {run}")

def daily_page(db,lat,lon):
    frame=prices(db)
    if frame.empty:st.info("Import daily reports first.");return
    st.caption("Decision at 00:00 IST before the session. Entry uses the observed session open. Exit uses the close of the selected observed session. Pre-launch history is excluded from testing.")
    st.plotly_chart(px.line(frame,x="day",y="close",title="NIFTY 50 spot index · daily close"))
    h=st.selectbox("Holding period in observed sessions",[1,2,5,10,20])
    first=st.number_input("First held-out year",1997,2100,2016)
    minimum=st.number_input("Minimum training observations",1,1000,20)
    key=st.selectbox("Pattern",["score","majority","day_lord","moon_star","moon_sub","moon_sign","lagna","signature"])
    data=joined_daily(db,frame,h,lat,lon)
    data=data[data.day>=pd.Timestamp("1996-04-22")].copy()
    if data.empty:
        st.info("Build midnight configurations for these coordinates in the historical pattern finder.");return
    data["signature"]=data[["day_lord",*FACTORS[1:]]].agg("|".join,axis=1)
    out=walk_forward(data,key,minimum,first,h)
    if out.empty:st.info("No eligible held-out cases.");return
    out["correct"]=out.actual==out.prediction
    out["baseline_correct"]=out.actual==out.baseline
    yearly=out.groupby(out.day.dt.year).agg(cases=("day","size"),accuracy=("correct","mean"),baseline=("baseline_correct","mean"),mean_return_pct=("return_pct","mean"),volatility_pct=("return_pct","std"))
    st.write(f"{len(out):,} non-overlapping held-out outcomes · Accuracy {out.correct.mean():.1%} · Training-mode baseline {out.baseline_correct.mean():.1%}")
    delta=(out.correct.astype(int)-out.baseline_correct.astype(int)).groupby(out.day.dt.to_period("M")).mean()
    if len(delta)>1:
        rng=np.random.default_rng(42)
        lo,hi=np.quantile([rng.choice(delta,len(delta)).mean() for _ in range(1500)],[.025,.975])
        st.caption(f"Equal-weight monthly accuracy advantage, 95% month-cluster bootstrap: {lo:+.1%} to {hi:+.1%}. Training expands each January and uses only completed prior outcomes.")
    st.plotly_chart(px.bar(yearly.reset_index(),x="day",y=["accuracy","baseline"],barmode="group"))
    st.dataframe(yearly)
    table(out,"daily_walk_forward")
    if st.button("Save backtest report locally"):
        path=ROOT/"reports"
        path.mkdir(exist_ok=True)
        from historical import save_report
        save_report(db,"daily",out,dict(model=MODEL,holding_sessions=h,rule=key,minimum=minimum,first_test_year=first,latitude=lat,longitude=lon))
        st.success("Saved in archive/reports")

def broker(bars):
    st.subheader("Upstox minute history")
    st.caption(f"{KEY} · Optional token storage uses Windows Credential Manager.")
    from keyring.backends.Windows import WinVaultKeyring
    vault=WinVaultKeyring()
    entered=st.text_input("Upstox access token",type="password")
    if entered and st.button("Remember token in Windows Credential Manager"):
        vault.set_password("NIFTY KP Terminal","Upstox",entered)
        st.success("Token stored for this Windows account")
    token=entered or os.getenv("UPSTOX_ACCESS_TOKEN") or vault.get_password("NIFTY KP Terminal","Upstox")
    today=pd.Timestamp.now(tz=IST).date()
    if st.button("Verify instrument"):
        st.json(verify_instrument())
    if not token:st.info("Offline research is available. Connect an activated account to request minute candles.");return
    if st.button("Test connection"):
        verify_instrument()
        body=fetch(token,today,today,current=True)
        st.success(f"API accepted the connection · {len(body['data']['candles'])} candles returned")
    action=st.radio("Update scope",["Sync latest","Download or repair a date range"])
    with connect() as db:
        last=db.execute("SELECT max(timestamp) FROM intraday WHERE source='Upstox 1m'").fetchall()[0][0]
        end_batch=db.execute("SELECT max(end_day) FROM broker_batches").fetchall()[0][0]
    starts=[x for x in (last.date() if last else None,end_batch) if x]
    latest=max(starts) if starts else today-timedelta(days=6)
    dates=st.date_input("Minute history range",(latest,today),min_value=date(2022,1,1)) if action.startswith("Download") else (latest,today)
    if st.button("Fetch minute candles") and len(dates)==2:
        for a,b,n in sync_minutes(token,*dates,INTRADAY,repair=action.startswith("Download")):st.write(f"{a} through {b} · {n:,} validated candles")


def daily_lab(db,lat,lon):
    from scipy.stats import binomtest
    frame=prices(db)
    if frame.empty:st.info("Import daily observations to start the research lab.");return
    # All context is lagged one observed trading date before the midnight decision.
    prior=frame.close.shift()
    frame["momentum"]=np.sign(prior-frame.close.shift(6))
    frame["volatility"]=np.floor(frame.close.pct_change().rolling(20).std().shift()*100)
    frame["previous_gap"]=np.sign((frame.open/frame.close.shift()-1).shift())
    vix=db.sql("select day,close as vix from daily where instrument='INDIA VIX'").df()
    frame=frame.merge(vix,on="day",how="left").sort_values("day")
    frame["vix_band"]=np.floor(frame.vix.shift()/5)
    frame["trend_regime"]=np.sign(prior-frame.close.rolling(100).mean().shift())
    data=joined_daily(db,frame,1,lat,lon)
    data=data[data.day>=pd.Timestamp("1996-04-22")].copy()
    if data.empty:st.info("Build midnight snapshots in the finder first.");return
    first=st.number_input("First held-out year",1997,2100,2016)
    minimum=st.number_input("Minimum previous observations",1,1000,20)
    factors=st.multiselect("Factors to compare",["day_lord","moon_star","moon_sub","lagna","majority","B12","momentum","volatility","previous_gap","vix_band","trend_regime"],default=["moon_star","momentum","volatility","vix_band"])
    reference=walk_forward(data,"score",minimum,first,1)
    if reference.empty:st.info("No eligible KP baseline cases in the selected period.");return
    reference=reference.set_index("day")
    rows=[]
    for factor in factors:
        subset=data.dropna(subset=[factor]).copy()
        subset["pattern"]=subset.score.astype(str)+"|"+subset[factor].astype(str)
        result=walk_forward(subset,"pattern",minimum,first,1)
        if result.empty:continue
        pairs=result.set_index("day").join(reference.prediction.rename("kp_only"),how="inner")
        if pairs.empty:continue
        correct=pairs.actual.eq(pairs.prediction)
        base=pairs.actual.eq(pairs.kp_only)
        monthly=(correct.astype(int)-base.astype(int)).groupby(pairs.index.to_period("M")).mean()
        n=int(monthly.ne(0).sum())
        p=binomtest(int(monthly.gt(0).sum()),n,.5,alternative="greater").pvalue if n else 1
        rows.append(dict(factor=factor,sessions=len(pairs),combined=correct.mean(),kp_only=base.mean(),
                         market_only=pairs.actual.eq(pairs.baseline).mean(),adjusted_p=min(1,p*11)))
    st.caption("Annual expanding training windows. Each comparison uses the same held-out dates for the combined rule, KP score and training-wide market baseline. Market variables use prior sessions. Monthly win counts use a one-sided sign test adjusted across the full family of 11 comparisons.")
    if rows:
        results=pd.DataFrame(rows)
        st.plotly_chart(px.bar(results,x="factor",y=["combined","kp_only","market_only"],barmode="group"))
        table(results,"daily_factor_comparison")
    else:st.info("No matched held-out observations for these settings.")

def auto_settings():
    import json
    settings=ROOT/"auto_sync.json"
    config=json.loads(settings.read_text()) if settings.exists() else {}
    with st.expander("Automatic updates while the terminal is open"):
        daily=st.checkbox("Check completed daily reports every 30 minutes",value=config.get("daily",False))
        minute=st.checkbox("Sync Upstox minutes using a saved token every 30 minutes",value=config.get("minute",False))
        if st.button("Save update preferences"):
            settings.write_text(json.dumps(dict(daily=daily,minute=minute)),encoding="utf8")
            st.rerun()

@st.fragment(run_every="30m")
def background_sync():
    import json
    settings=ROOT/"auto_sync.json"
    if not settings.exists():return
    prefs=json.loads(settings.read_text())
    if not any(prefs.values()):return
    now=pd.Timestamp.now(tz=IST)
    stamp=ROOT/"last_auto_attempt.txt"
    if stamp.exists() and (now-pd.Timestamp(stamp.read_text())).total_seconds()<1750:return
    stamp.write_text(now.isoformat())
    try:
        if prefs.get("daily"):
            with connect() as db:
                last=db.execute("SELECT max(day) FROM trading_dates").fetchall()[0][0]
                end=now.date()-timedelta(days=1)
                for day,status in sync(db,(last+timedelta(days=1)) if last else end,end):
                    if status=="validated":
                        base=pd.Timestamp(day,tz=IST)
                        list(build(db,[base,base+pd.Timedelta(hours=9,minutes=15),base+pd.Timedelta(hours=10,minutes=30)]))
        if prefs.get("minute"):
            from keyring.backends.Windows import WinVaultKeyring
            token=os.getenv("UPSTOX_ACCESS_TOKEN") or WinVaultKeyring().get_password("NIFTY KP Terminal","Upstox")
            if token:
                with connect() as db:
                    last=db.execute("SELECT max(end_day) FROM broker_batches").fetchall()[0][0]
                list(sync_minutes(token,last or now.date()-timedelta(days=5),now.date(),INTRADAY))
    except Exception as e:
        st.warning(f"Automatic update paused until next check. {e}")
