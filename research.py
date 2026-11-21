"""Local candle storage and chronological research calculations."""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from kp_engine import KPChart, PLANETS, IST, LAT, LON

DB = Path(__file__).with_name("candles.sqlite3")
FACTORS = ["day", "moon_sign", "moon_star", "moon_sub", "lagna"]

def prepare(raw, mapping, zone, interval, start_label, special):
    bars = raw[list(mapping)].rename(columns=mapping).copy()
    def timestamp(value):
        t = pd.Timestamp(value)
        if pd.isna(t):
            raise ValueError("Missing timestamp")
        if t.tzinfo is None:
            t = t.tz_localize(zone, ambiguous="raise", nonexistent="raise")
        return t.tz_convert(IST) + pd.Timedelta(minutes=interval if start_label else 0)
    bars["timestamp"] = bars.timestamp.map(timestamp)
    for col in ["open","high","low","close"]:
        if col in bars:
            bars[col] = pd.to_numeric(bars[col])
            if not (np.isfinite(bars[col]) & (bars[col]>0)).all():
                raise ValueError(f"Invalid {col} price")
        else:
            bars[col] = np.nan
    if (bars.high < bars[["low","open","close"]].max(axis=1)).any() or (bars.low > bars[["high","open","close"]].min(axis=1)).any():
        raise ValueError("Inconsistent OHLC range")
    t = bars.timestamp.dt
    if (t.second.ne(0) | t.microsecond.ne(0)).any():
        raise ValueError("Expected minute-aligned timestamps")
    if not special and ((t.weekday>=5) | ~(t.hour*60+t.minute).between(555,930)).any():
        raise ValueError("Outside standard weekday session. Verify special session or timestamp convention.")
    bars = bars.drop_duplicates().sort_values("timestamp")
    if bars.timestamp.duplicated().any():
        raise ValueError("Conflicting prices at one timestamp")
    return bars

def connection(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS candles(timestamp TEXT PRIMARY KEY, open REAL, high REAL, low REAL, close REAL NOT NULL, source TEXT)")
    return db

def save(bars, source, path=DB):
    with connection(path) as db:
        for row in bars.itertuples():
            values = tuple(None if pd.isna(v) else v for v in (row.open,row.high,row.low,row.close))
            key = row.timestamp.isoformat()
            prior = db.execute("SELECT open,high,low,close FROM candles WHERE timestamp=?", (key,)).fetchone()
            if prior and prior != values:
                raise ValueError(f"Existing candle conflicts at {key}. Import cancelled.")
            db.execute("INSERT OR IGNORE INTO candles VALUES(?,?,?,?,?,?)",(key,*values,source))

def read(path=DB):
    with connection(path) as db:
        bars = pd.read_sql("SELECT * FROM candles ORDER BY timestamp",db)
    bars["timestamp"] = pd.to_datetime(bars.timestamp,utc=True).dt.tz_convert(IST)
    return bars.set_index("timestamp")

def feature(t,lat=LAT,lon=LON):
    chart = KPChart(t,lat,lon)
    result = chart.calculate()
    return dict(timestamp=t,score=result["kp_score"],majority=result["majority"],**result["ruling_planets"],
                **{p:chart.longitude(p) for p in PLANETS})

def events(bars,horizon,lat=LAT,lon=LON,nonoverlap=True):
    rows=[]
    previous_close=None
    for day,g in bars.groupby(bars.index.date):
        close=g.close
        change=close.pct_change()
        vol=change.rolling(5).std()
        opening=g.open.iloc[0]
        gap=np.sign(opening-previous_close) if previous_close and g.index[0].strftime("%H:%M") in ("09:15","09:16") else np.nan
        previous_close=close.iloc[-1] if g.index[-1].strftime("%H:%M")=="15:30" else None
        next_free=None
        for i,t in enumerate(g.index):
            end=t+pd.Timedelta(minutes=horizon)
            if (nonoverlap and next_free and t<next_free) or end not in close.index:
                continue
            if "interval_minutes" in g:
                interval=int(g.interval_minutes.iloc[i])
                exit_i=close.index.get_loc(end)
                if horizon%interval or exit_i-i!=horizon//interval:
                    continue
                window=g.iloc[i:exit_i+1]
                if not window.interval_minutes.eq(interval).all() or not (window.index.to_series().diff().dropna()==pd.Timedelta(minutes=interval)).all():
                    continue
            row=feature(t,lat,lon)
            r=100*(close[end]/close[t]-1)
            rows.append(dict(**row,date=day,close=close[t],exit_price=close[end],return_pct=r,
                             outcome=int(np.sign(r)),trend=np.sign(change.iloc[i]),gap=gap,
                             volatility=np.floor(vol.iloc[i]*1000),hour=t.hour))
            next_free=end
    return pd.DataFrame(rows)

def evaluate(data,split,keys,minimum,cost):
    train=data[data.date<split].dropna(subset=keys)
    test=data[data.date>=split].dropna(subset=keys)
    if train.empty or test.empty:
        return pd.DataFrame()
    stats=train.groupby(keys).agg(sessions=("date","nunique"),prediction=("outcome",lambda a:a.mode().iat[0]))
    out=test.join(stats[stats.sessions>=minimum],on=keys,how="inner").sort_values("timestamp").copy()
    out["baseline"]=train.outcome.mode().iat[0]
    out["net_pct"]=out.prediction*out.return_pct-out.prediction.abs()*cost/100
    out["equity"]=(1+out.net_pct/100).cumprod()
    return out
