"""Research operations reused by the custom API."""
from datetime import date
import pandas as pd
import numpy as np
from kp_engine import IST
from historical import cached,daily_outcomes,walk_forward
from minute_archive import bars_for
from research import events,evaluate,FACTORS

def backtest(con,start,end,split,horizon,minimum,cost,mode,key):
    if mode=="daily":
        prices=con.execute("SELECT * FROM daily WHERE instrument='NIFTY 50' AND day BETWEEN ? AND ? ORDER BY day",[start,end]).df()
        if prices.empty:return pd.DataFrame()
        from datetime import time
        feat=cached(con,start,end,decision=time(0))
        feat["session"]=feat.timestamp.dt.date
        prices["session"]=prices.day.dt.date
        data=daily_outcomes(prices,horizon).merge(feat.rename(columns={"day":"day_lord"}),on="session")
        return walk_forward(data,key,minimum,split.year,horizon)
    bars=bars_for(con,pd.Timestamp(start,tz=IST),pd.Timestamp(end,tz=IST)+pd.Timedelta(days=1))
    data=events(bars,horizon)
    if data.empty:return pd.DataFrame()
    return evaluate(data,split,[key],minimum,cost)

def factor_lab(con,first,minimum):
    from scipy.stats import binomtest
    from datetime import time
    frame=con.sql("select * from daily where instrument='NIFTY 50' order by day").df()
    if frame.empty:return []
    prior=frame.close.shift()
    frame["momentum"]=np.sign(prior-frame.close.shift(6))
    frame["volatility"]=np.floor(frame.close.pct_change().rolling(20).std().shift()*100)
    frame["previous_gap"]=np.sign((frame.open/frame.close.shift()-1).shift())
    vix=con.sql("select day,close as vix from daily where instrument='INDIA VIX'").df()
    frame=frame.merge(vix,on="day",how="left").sort_values("day")
    frame["vix_band"]=np.floor(frame.vix.shift()/5)
    frame["trend_regime"]=np.sign(prior-frame.close.rolling(100).mean().shift())
    feat=cached(con,frame.day.min().date(),frame.day.max().date(),decision=time(0))
    feat["session"]=feat.timestamp.dt.date
    frame["session"]=frame.day.dt.date
    data=daily_outcomes(frame,1).merge(feat.rename(columns={"day":"day_lord"}),on="session")
    data=data[data.day>=pd.Timestamp("1996-04-22")].copy()
    reference=walk_forward(data,"score",minimum,first,1)
    if reference.empty:return []
    reference=reference.set_index("day")
    rows=[]
    for factor in ["day_lord","moon_star","moon_sub","lagna","majority","B12","momentum","volatility","previous_gap","vix_band","trend_regime"]:
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
        rows.append(dict(factor=factor,sessions=len(pairs),combined=float(correct.mean()),kp_only=float(base.mean()),market_only=float(pairs.actual.eq(pairs.baseline).mean()),adjusted_p=min(1,float(p)*11)))
    return rows

