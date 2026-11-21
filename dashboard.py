from datetime import date, datetime, time
from itertools import combinations
from pathlib import Path
from zoneinfo import available_timezones
import subprocess
import sys
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import swisseph as swe
from scipy.stats import binomtest
from kp_engine import KPChart, IST, LAT, LON, PLANETS, slots, star_lord, sub_lord, sign_lord
from historical import connect as archive_connection
import archive_ui
from research import DB, FACTORS, prepare, save, read, feature, events, evaluate

ROOT=Path(__file__).parent
PAGES=["Overview","KP calculator","Intraday timeline","Historical pattern finder","Historical backtesting","NIFTY data manager","Research lab","Settings and diagnostics","Daily research","Data health","Upstox connection"]
st.set_page_config(page_title="NIFTY 50 — KP Astro Market Research Terminal",layout="wide")
st.sidebar.title("NIFTY 50")
st.sidebar.caption("KP Astro Market Research Terminal")
page=st.sidebar.radio("Workspace",PAGES,key="page")
def navigate(destination):
    st.session_state.page=destination
st.sidebar.divider()
day=st.sidebar.date_input("Chart date",date.today(),min_value=date(1900,1,1))
clock=st.sidebar.time_input("Chart time",time(10,30))
horizon=st.sidebar.selectbox("Forward horizon (minutes)",[5,15,30,60],index=1)
with st.sidebar.expander("Chart location and timezone"):
    lat=st.number_input("Latitude", -89.,89.,LAT,format="%.4f")
    lon=st.number_input("Longitude",-180.,180.,LON,format="%.4f")
    zones=sorted(available_timezones())
    zone=st.selectbox("Input timezone",zones,index=zones.index("Asia/Kolkata"))
try:
    ts=pd.Timestamp(datetime.combine(day,clock)).tz_localize(zone).tz_convert(IST)
    chart=KPChart(ts,lat,lon)
    kp=chart.calculate()
except Exception as e:
    st.error(str(e))
    st.stop()
demo=st.sidebar.toggle("Synthetic demo",help="Separate demonstration database with invented prices.")
active_db=DB.with_name("demo.sqlite3") if demo else DB
if demo:
    st.sidebar.info("Synthetic demonstration prices")
    if read(active_db).empty:
        sample=pd.read_csv(ROOT/"examples"/"synthetic_demo.csv")
        save(prepare(sample,{c:c for c in sample},"Asia/Kolkata",5,False,False),"Synthetic demo",active_db)
if demo:
    bars=read(active_db)
else:
    from minute_archive import schema,bars_for,store_bars,attach_prices
    with archive_connection() as adb:
        schema(adb)
        count,minute_first,minute_last=adb.execute("SELECT count(*),min(timestamp),max(timestamp) FROM intraday").fetchall()[0]
        first_day=last_day=ts.date()
        if page==PAGES[6] and st.sidebar.radio("Research frequency",["Daily","Intraday"])=="Daily":
            st.title("Research lab · daily observations")
            archive_ui.daily_lab(adb,lat,lon)
            st.stop()
        if count and page in (PAGES[4],PAGES[6]):
            default_start=max(minute_first.date(),minute_last.date()-pd.Timedelta(days=60))
            selection=st.sidebar.date_input("Intraday study dates",(default_start,minute_last.date()),min_value=minute_first.date(),max_value=minute_last.date())
            if len(selection)!=2:st.stop()
            first_day,last_day=selection
        if count and page in (PAGES[5],PAGES[9],PAGES[10]):
            first_day=last_day=minute_last.date()
        begin=pd.Timestamp(first_day,tz=IST)
        finish=pd.Timestamp(last_day,tz=IST)+pd.Timedelta(days=1)
        bars=bars_for(adb,begin,finish)
st.title("NIFTY 50 — KP Astro Market Research Terminal" if page==PAGES[0] else page)
st.caption(f"{ts:%d %b %Y · %H:%M IST}   /   {horizon}-minute horizon")
@st.cache_data(max_entries=6)
def get_events(data,h,a,b,nonoverlap=True):
    return events(data,h,a,b,nonoverlap)
def export(df,name):
    st.dataframe(df,hide_index=True,width="stretch")
    st.download_button("Download CSV",df.to_csv(index=False),name+".csv","text/csv")
def measures(items):
    for col,(label,value) in zip(st.columns(len(items)),items):
        col.metric(label,value)
def summary(df):
    measures([("Matches",len(df)),("Up",f"{(df.outcome>0).mean():.1%}"),("Down",f"{(df.outcome<0).mean():.1%}"),("Mean return",f"{df.return_pct.mean():+.3f}%")])
def history(data):
    if data.empty:
        st.info("No eligible price windows. Import timestamped candles in NIFTY data manager.")
        st.stop()
def line(df,y):
    st.plotly_chart(px.line(df,x="timestamp",y=y),width="stretch")
if not demo:
    archive_ui.background_sync()
if not demo and page in (PAGES[3],PAGES[8],PAGES[9],PAGES[10]):
    try:
        with archive_connection() as adb:
            if page==PAGES[3]: archive_ui.archive_search(adb,ts,lat,lon,horizon,bars)
            elif page==PAGES[8]: archive_ui.daily_page(adb,lat,lon)
            elif page==PAGES[9]:
                archive_ui.auto_settings()
                archive_ui.health(adb,bars)
            else: archive_ui.broker(bars)
    except Exception as e:
        st.error(str(e))
    st.stop()
if demo and page in PAGES[8:]:
    st.info("Switch off Synthetic demo to access the production archive.")
    st.stop()
if page==PAGES[0]:
    if not demo:
        with archive_connection() as adb:
            n,earliest,latest=adb.execute("SELECT count(*),min(day),max(day) FROM trading_dates").fetchall()[0]
            matches=adb.execute("""SELECT count(*) FROM snapshots WHERE ts::DATE<? AND ts::TIMESTAMP::TIME=CAST(? AS TIME) AND lat=? AND lon=?
                AND model=? AND json_extract_string(details,'$.signature')=?""",[ts.date(),str(ts.time()),lat,lon,archive_ui.MODEL,kp["signature"]]).fetchall()[0][0]
        st.caption(f"Daily archive · {n:,} NIFTY 50 sessions · {earliest} through {latest}")
        st.caption(f"Intraday archive · {count:,} candles · {minute_first} through {minute_last}")
        st.write(f"{matches:,} earlier saved configurations match all five ruling planets at this IST clock time.")
        st.button("Open daily walk-forward research",on_click=navigate,args=(PAGES[8],))
    score=kp["kp_score"]
    measures([("KP score",score),("Score classification","Favourable" if score>0 else "Unfavourable" if score<0 else "Mixed"),("Market","NIFTY 50")])
    st.subheader("Ruling planets")
    measures(list(kp["ruling_planets"].items()))
    st.button("Find historical matches",on_click=navigate,args=(PAGES[3],))
    if not demo:
        with archive_connection() as adb:
            targets=adb.execute("""SELECT ts AS timestamp FROM snapshots WHERE ts::DATE<? AND ts::TIMESTAMP::TIME=CAST(? AS TIME) AND lat=? AND lon=?
                AND model=? AND json_extract_string(details,'$.signature')=?""",[ts.date(),str(ts.time()),lat,lon,archive_ui.MODEL,kp["signature"]]).df()
            matched=attach_prices(adb,targets,horizon).dropna()
        if len(matched):
            returns=100*(matched.exit_price/matched.close-1)
            measures([("Priced matches",len(returns)),("Up",f"{(returns>0).mean():.1%}"),("Down",f"{(returns<0).mean():.1%}"),("Mean return",f"{returns.mean():+.3f}%")])
        else:st.info("No complete intraday return windows for this saved configuration and clock time.")
    elif bars.empty:
        st.info("No intraday candles imported. Daily index history is available in Daily research.")
    else:
        st.caption(f"Latest candle {bars.index.max()} · Sources: {', '.join(bars.source.unique())}")
        data=get_events(bars[bars.index.date<ts.date()],horizon,lat,lon,False)
        history(data)
        matches=data[(data[FACTORS]==pd.Series(kp["ruling_planets"])).all(axis=1)]
        if len(matches): summary(matches)
        else: st.info("No prior exact matches.")
elif page==PAGES[1]:
    if st.button("Calculate KP",type="primary") or st.session_state.get("calculated")==str((ts,lat,lon)):
        st.session_state.calculated=str((ts,lat,lon))
        st.metric("Final KP score",kp["kp_score"])
        st.caption("Gain houses 2, 6, 10, 11 · Loss houses 5, 8, 12. Each ruling factor compares the number of distinct houses in each set.")
        st.dataframe(kp["ruling_details"])
        names="Ashwini Bharani Krittika Rohini Mrigashira Ardra Punarvasu Pushya Ashlesha Magha Purva-Phalguni Uttara-Phalguni Hasta Chitra Swati Vishakha Anuradha Jyeshtha Mula Purva-Ashadha Uttara-Ashadha Shravana Dhanishta Shatabhisha Purva-Bhadrapada Uttara-Bhadrapada Revati".split()
        rows=[]
        for p in PLANETS:
            x=chart.longitude(p)
            rows.append(dict(planet=p,longitude=x,nakshatra=names[int(x/(360/27))],star=star_lord(x),sub=sub_lord(x),sign=sign_lord(x),houses=str(sorted(chart.significator_houses(p)))))
        st.subheader("Sidereal positions")
        st.dataframe(rows)
        labels=["Gain factors × 2","Loss factors × −2","Directional Moon sub × 1","Either majority × 2","Moon sub confirms majority × 3","Lagna confirms majority × 2","Mixed factors × −2"]
        st.subheader("Score calculation")
        st.table([dict(cell=k,rule=l,contribution=v*(-1 if k in ("B13","B18") else 1)) for (k,v),l in zip(kp["components"].items(),labels)])
        st.button("Find historical matches",on_click=navigate,args=(PAGES[3],))
elif page==PAGES[2]:
    step=st.selectbox("Interval (minutes)",[1,5,15,30],index=2)
    times=list(slots(ts.date(),step))
    finish=times[0].replace(hour=15,minute=30)
    if times[-1]!=finish: times.append(finish)
    if not demo and len(bars):
        times=list(pd.date_range(bars.index.min(),bars.index.max(),freq=f"{step}min").union([bars.index.max()]))
        finish=bars.index.max()
        st.caption("Sampled from the first to last observed candle close in this session.")
    elif not demo:
        st.caption("Illustrative 09:15–15:30 IST observation grid. Historical trading hours are unverified for this date.")
    df=pd.DataFrame([feature(t,lat,lon) for t in times]).drop(columns=list(PLANETS))
    df["close"]=bars.close.reindex(times).to_numpy()
    future=bars.close.reindex(pd.DatetimeIndex(times)+pd.Timedelta(minutes=horizon)).to_numpy()
    df["forward_return_pct"]=np.where(df.timestamp+pd.Timedelta(minutes=horizon)<=finish,100*(future/df.close-1),np.nan)
    if not demo and len(bars):
        with archive_connection() as adb:
            observed=attach_prices(adb,df[["timestamp"]],horizon)
        df["forward_return_pct"]=100*(observed.exit_price/observed.close-1)
    df["transition"]=df[FACTORS+["majority"]].ne(df[FACTORS+["majority"]].shift()).apply(lambda r:", ".join(r.index[r]),axis=1)
    fig=px.line(df,x="timestamp",y="score",hover_data=FACTORS+["majority","transition"])
    changes=df[df.transition.ne("")]
    fig.add_scatter(x=changes.timestamp,y=changes.score,mode="markers",name="Configuration change",text=changes.transition)
    st.plotly_chart(fig)
    if df.close.notna().any(): line(df,"close")
    else: st.info("No prices at the selected session timestamps.")
    export(df,"timeline")
elif page==PAGES[5]:
    if not demo:
        st.button("View daily sources and sync reports",on_click=navigate,args=(PAGES[9],))
    st.caption("Local SQLite storage · Import licensed index candles. The supplied example contains synthetic prices.")
    file=st.file_uploader("Historical candles",type="csv")
    if file:
        try:
            raw=pd.read_csv(file)
            mapping={}
            for field in ["timestamp","close","open","high","low"]:
                opts=(["(skip)"] if field not in ("timestamp","close") else [])+list(raw.columns)
                default=next((n for n in opts if n.lower()==field),opts[0])
                col=st.selectbox(field,opts,index=opts.index(default))
                if col!="(skip)":
                    if col in mapping: raise ValueError("Choose distinct columns")
                    mapping[col]=field
            source_zone=st.selectbox("Timezone of offset-free timestamps",zones,index=zones.index("Asia/Kolkata"))
            interval=st.number_input("Candle interval (minutes)",1,375,1)
            start=st.checkbox("Labels indicate candle starts")
            special=st.checkbox("Allow verified special-session timestamps outside regular hours")
            clean=prepare(raw,mapping,source_zone,interval,start,special)
            if clean.empty: raise ValueError("CSV has no candles")
            gaps=clean.groupby(clean.timestamp.dt.date).timestamp.diff().dt.total_seconds()/60
            st.write(f"{len(clean):,} unique candles · {len(raw)-len(clean)} duplicates removed · {sum(gaps>interval)} internal gaps longer than {interval} min")
            st.dataframe(clean.head(50))
            if st.button("Import into database",type="primary"):
                if demo:
                    save(clean,file.name,active_db)
                else:
                    import hashlib
                    from historical import RAW
                    raw_path=RAW/("user-"+hashlib.sha256(file.getvalue()).hexdigest()+".csv")
                    raw_path.write_bytes(file.getvalue())
                    with archive_connection() as adb:
                        store_bars(adb,clean,file.name,str(raw_path),"User import", "start" if start else "close",interval)
                st.success("Import complete")
                bars=read(active_db) if demo else clean.set_index("timestamp")
        except Exception as e: st.error(str(e))
    if len(bars):
        if not demo:
            st.write(f"{count:,} stored intraday candles · {minute_first} through {minute_last}")
        st.caption("Most recent candles in the preview")
        st.dataframe(bars.tail(30))
elif page==PAGES[7]:
    if not demo:
        with archive_connection() as adb:
            st.write(f"Historical model {archive_ui.MODEL}")
            st.dataframe(archive_ui.coverage(adb))
            st.write(f"{adb.execute('SELECT count(*) FROM snapshots').fetchall()[0][0]:,} stored KP records")
        st.caption("Primary keys enforce unique timestamps per chart setting and unique dates per daily instrument.")
    flags=swe.calc_ut(chart.jd,swe.MOON,chart.flags)[1]
    st.table(dict(Setting=["Engine","Swiss Ephemeris","Moon calculation","Library file path","Reference","Database","Storage","Appearance"],Value=["0.1",swe.version,"Moshier" if flags&swe.FLG_MOSEPH else "Swiss files",str(swe.get_current_file_data(0)[0] or "Built-in fallback"),"Jaipur · 26.9124 N, 75.7873 E · Lahiri · Placidus · Mean node · Asia/Kolkata",str(active_db if demo else ROOT/"archive/research.duckdb"),f"{len(bars) if demo else count} candles","App menu → Settings → Theme"]))
    log=ROOT/"diagnostics.txt"
    if st.button("Run diagnostics"):
        run=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=ROOT,capture_output=True,text=True)
        log.write_text(str(datetime.now(IST))+"\n"+run.stdout+run.stderr,encoding="utf8")
    if log.exists(): st.code(log.read_text(encoding="utf8"))
else:
    if not demo and page in (PAGES[4],PAGES[6]):
        st.button("Use real daily index observations",on_click=navigate,args=(PAGES[8],))
    if bars.empty:
        st.info("Import candles in NIFTY data manager to start historical research.")
        st.button("Open data manager",on_click=navigate,args=(PAGES[5],))
        st.stop()
    dates=st.date_input("Historical date range",(bars.index.min().date(),bars.index.max().date()),min_value=date(1900,1,1))
    if len(dates)!=2: st.stop()
    selected=bars[(bars.index.date>=dates[0]) & (bars.index.date<=dates[1])]
    if page==PAGES[3]: selected=selected[selected.index.date<ts.date()]
    data=get_events(selected,horizon,lat,lon,page!=PAGES[3])
    history(data)
    if not demo:st.caption("Session eligibility uses a retrospective data-quality check. Coverage and selection can affect measured performance.")
    st.caption("Windows use exact observed endpoints on one IST date. Finder includes overlapping historical occurrences. Backtesting and lab use non-overlapping windows.")
    if page==PAGES[3]:
        mode=st.radio("Matching rule",["Exact","Partial","Astronomical similarity (experimental)"],horizontal=True)
        mask=pd.Series(True,index=data.index)
        if mode=="Partial":
            keys=st.multiselect("Required factors",FACTORS,default=["moon_star"])
            n=st.slider("Minimum matching factors overall",1,5,1)
            mask &= (data[FACTORS]==pd.Series(kp["ruling_planets"])).sum(axis=1)>=n
            if st.checkbox("Require same majority"): mask &= data.majority==kp["majority"]
            if st.checkbox("Require same score"): mask &= data.score==kp["kp_score"]
        elif mode=="Exact": keys=FACTORS
        else:
            keys=[]
            planets=st.multiselect("Bodies",PLANETS,default=["Moon","Sun"])
            tolerance=st.slider("Angular tolerance (degrees)",0.1,180.,5.)
            if not planets: st.stop()
            def distance(a,b): return abs((a-b+180)%360-180)
            for p in planets: mask &= distance(data[p],chart.longitude(p))<=tolerance
            for p,q in combinations(planets,2):
                mask &= abs(distance(data[p],data[q])-distance(chart.longitude(p),chart.longitude(q)))<=tolerance
        for k in keys: mask &= data[k]==kp["ruling_planets"][k]
        matches=data[mask]
        minimum=st.number_input("Minimum sample size",1,10000,10)
        if len(matches)>=minimum: summary(matches)
        else: st.info(f"{len(matches)} matches, below the selected reporting minimum.")
        export(matches,"historical_matches")
        st.button("Run backtest",on_click=navigate,args=(PAGES[4],))
    else:
        days=sorted(data.date.unique())
        split=st.date_input("First out-of-sample date",days[min(len(days)-1,int(len(days)*0.7))],min_value=date(1900,1,1))
        minimum=st.number_input("Minimum distinct training sessions per pattern",1,10000,5)
        cost=st.number_input("Round-trip cost (basis points)",0.,1000.,2.)
        st.caption("Each pattern predicts its most frequent training outcome (ties select the lower outcome). Up goes long, down short, flat stays in cash. Baseline uses the training-wide mode.")
        if page==PAGES[4]:
            keys=st.multiselect("Matching factors",["score"]+FACTORS,default=["score"])
            regime=st.selectbox("Previous observed bar trend",["All","Rising","Falling"])
            if regime!="All": data=data[data.trend==(1 if regime=="Rising" else -1)]
            if not keys: st.stop()
            validation=st.radio("Validation",["Fixed split","Monthly expanding training window"],horizontal=True)
            if validation=="Fixed split":
                out=evaluate(data,split,keys,minimum,cost)
            else:
                folds=[]
                test_days=data.loc[data.date>=split,"timestamp"].dt.tz_localize(None).dt.to_period("M")
                for month in sorted(test_days.unique()):
                    cutoff=max(split,month.start_time.date())
                    fold=evaluate(data[data.date<=month.end_time.date()],cutoff,keys,minimum,cost)
                    if len(fold):folds.append(fold)
                out=pd.concat(folds).sort_values("timestamp") if folds else pd.DataFrame()
                if len(out):out["equity"]=(1+out.net_pct/100).cumprod()
            if out.empty: st.info("No qualifying held-out observations. Check coverage, rule and split.")
            else:
                summary(out)
                out["gross_pct"]=out.prediction*out.return_pct
                out["benchmark_pct"]=out.baseline*out.return_pct-out.baseline.abs()*cost/100
                out["correct"]=out.prediction==out.outcome
                out["baseline_correct"]=out.baseline==out.outcome
                yearly=out.groupby(out.timestamp.dt.year).agg(windows=("outcome","size"),accuracy=("correct","mean"),baseline=("baseline_correct","mean"),return_volatility_pct=("return_pct","std"),mean_net_pct=("net_pct","mean"))
                st.dataframe(yearly)
                st.caption(f"Active positions {out.prediction.ne(0).sum()} of {len(out)} matched windows · Gross compounded return {((1+out.gross_pct/100).prod()-1):.2%} · Same-window baseline after costs {((1+out.benchmark_pct/100).prod()-1):.2%}")
                accuracy=(out.prediction==out.outcome).mean()
                measures([("Accuracy",f"{accuracy:.1%}"),("Baseline",f"{(out.baseline==out.outcome).mean():.1%}"),("Flat",f"{(out.outcome==0).mean():.1%}"),("Median return",f"{out.return_pct.median():+.3f}%")])
                daily=out.groupby("date").return_pct.mean()
                if len(daily)>1:
                    rng=np.random.default_rng(42)
                    ci=np.quantile([rng.choice(daily,len(daily)).mean() for _ in range(1000)],[.025,.975])
                    st.write(f"Day-weighted mean return, 95% session bootstrap interval: {ci[0]:.3f}% to {ci[1]:.3f}% ({len(daily)} sessions).")
                st.write(f"Maximum drawdown: {(out.equity/out.equity.cummax().clip(lower=1)-1).min():.2%} · Net compounded return: {out.equity.iloc[-1]-1:.2%}")
                line(out,"equity")
                st.plotly_chart(px.histogram(out,x="return_pct"))
                export(out,"out_of_sample_backtest")
        else:
            st.caption("Exploratory fixed comparisons. Session-level accuracy wins versus baseline exclude ties. Bonferroni adjustment covers the displayed family only. Repeated analysis of the same holdout requires fresh validation.")
            rules=[["score"]]+[[k] for k in FACTORS]+[FACTORS]+[["score",k] for k in ["trend","volatility","hour","gap"]]
            rows=[]
            for keys in rules:
                out=evaluate(data,split,keys,minimum,cost)
                if out.empty: continue
                hit=(out.prediction==out.outcome).astype(int)
                base=(out.baseline==out.outcome).astype(int)
                delta=(hit-base).groupby(out.date).mean()
                n=int((delta!=0).sum())
                p=binomtest(int((delta>0).sum()),n,.5,alternative="greater").pvalue if n else 1
                rows.append(dict(rule=" + ".join(keys),observations=len(out),sessions=len(delta),accuracy=hit.mean(),baseline=base.mean(),mean_net_pct=out.net_pct.mean(),adjusted_p=min(1,p*len(rules))))
            if rows: export(pd.DataFrame(rows),"exploratory_comparison")
            else: st.info("Insufficient training or test coverage for the selected rules.")
