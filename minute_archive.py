"""Import source-labelled minute starts after daily range reconciliation."""
from pathlib import Path
import numpy as np
import pandas as pd
from historical import ROOT,connect,IST

def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS intraday(timestamp TIMESTAMPTZ PRIMARY KEY,
       open DOUBLE,high DOUBLE,low DOUBLE,close DOUBLE,source VARCHAR,raw_file VARCHAR,quality VARCHAR,
       source_label VARCHAR,interval_minutes INTEGER,imported_at TIMESTAMPTZ DEFAULT now())""")
    db.execute("""CREATE TABLE IF NOT EXISTS broker_conflicts(timestamp TIMESTAMPTZ, source_file VARCHAR, existing_close DOUBLE, incoming_close DOUBLE,
        PRIMARY KEY(timestamp,source_file))""")
    db.execute("""CREATE TABLE IF NOT EXISTS broker_batches(start_day DATE,end_day DATE,raw_file VARCHAR,received BIGINT,imported_at TIMESTAMPTZ DEFAULT now(),PRIMARY KEY(start_day,end_day,raw_file))""")
    db.execute("""CREATE TABLE IF NOT EXISTS minute_audit(source_file VARCHAR,day DATE,bars INTEGER,
      high_difference DOUBLE,low_difference DOUBLE,status VARCHAR,PRIMARY KEY(source_file,day))""")

def store_bars(db,bars,source,path,quality,label,interval):
    incoming=bars[["timestamp","open","high","low","close"]].assign(source=source,raw_file=path,quality=quality,source_label=label,interval_minutes=interval)
    if db.execute("""SELECT count(*) FROM incoming i JOIN intraday d USING(timestamp)
        WHERE d.close IS DISTINCT FROM i.close OR d.open IS DISTINCT FROM i.open OR d.high IS DISTINCT FROM i.high OR d.low IS DISTINCT FROM i.low""").fetchall()[0][0]:
        raise ValueError("Conflicting candle at an existing timestamp. Import cancelled.")
    db.execute("INSERT INTO intraday BY NAME SELECT * FROM incoming ON CONFLICT DO NOTHING")

def load_file(db,file):
    name=str(file.relative_to(ROOT))
    raw=pd.read_csv(file)
    raw.columns=raw.columns.str.lower()
    raw["timestamp"]=pd.to_datetime(raw.timestamp).dt.tz_localize(IST)
    epoch=pd.to_datetime(raw.epoch,unit="s",utc=True)
    raw["valid"]=raw.timestamp.eq(epoch)&raw.timestamp.dt.second.eq(0)
    cols=["open","high","low","close"]
    raw["valid"] &= np.isfinite(raw[cols]).all(axis=1)&(raw[cols]>0).all(axis=1)&(raw.high>=raw[["open","close","low"]].max(axis=1))&(raw.low<=raw[["open","close"]].min(axis=1))
    raw=raw.drop_duplicates(subset=["timestamp",*cols]).copy()
    raw["valid"] &= ~raw.timestamp.duplicated(keep=False)
    raw["day"]=raw.timestamp.dt.tz_localize(None).dt.normalize()
    daily=db.sql("SELECT day,high,low FROM daily WHERE instrument='NIFTY 50' AND provider<>'Secondary ^NSEI archive'").df().set_index("day")
    audit=raw.groupby("day").agg(bars=("close","size"),high=("high","max"),low=("low","min"),valid=("valid","all"))
    for col in ["high","low"]:audit[col+"_difference"]=(audit[col]-daily[col].reindex(audit.index)).abs()
    ok=audit.valid & (audit.high_difference<=.100001)&(audit.low_difference<=.100001)
    audit["status"]=np.where(ok,"Range reconciled","Quarantined")
    audit["source_file"]=name
    audit=audit.reset_index()
    raw=raw[raw.day.isin(audit.loc[ok.to_numpy(),"day"])].copy()
    raw["timestamp"]+=pd.Timedelta(minutes=1)
    db.execute("BEGIN")
    try:
        store_bars(db,raw,"Technovus public archive",name,"Session high/low within 0.10 index points of NSE","minute start",1)
        db.execute("INSERT OR REPLACE INTO minute_audit SELECT source_file,day,bars,high_difference,low_difference,status FROM audit")
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise

def bars_for(db,start,end):
    return db.execute("""SELECT timestamp,open,high,low,close,source,interval_minutes FROM intraday WHERE timestamp>=? AND timestamp<? ORDER BY timestamp""",[start,end]).df().set_index("timestamp")

def attach_prices(db,df,horizon):
    targets=pd.DataFrame({"timestamp":df.timestamp})
    # Require every minute in the forward interval; holidays, breaks and gaps interrupt the window.
    lookup=db.execute("""SELECT t.timestamp,c.close,
        CASE WHEN count(b.timestamp)=? AND max(b.timestamp)::DATE=t.timestamp::DATE
             THEN arg_max(b.close,b.timestamp) END AS exit_price
        FROM targets t LEFT JOIN intraday c USING(timestamp)
        LEFT JOIN intraday b ON CAST(b.timestamp AS DATE)=CAST(t.timestamp AS DATE) AND b.timestamp>t.timestamp AND b.timestamp<=t.timestamp+?*INTERVAL '1 minute' AND b.interval_minutes=1
        GROUP BY t.timestamp,c.close""",[horizon,horizon]).df()
    return df.merge(lookup,on="timestamp",how="left")

if __name__=="__main__":
    with connect() as db:
        schema(db)
        for file in sorted((ROOT/"minute-source/1min").rglob("*.csv")):
            load_file(db,file)
        db.execute(f"COPY intraday TO '{(ROOT/'intraday.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        print(db.sql("SELECT count(*),min(timestamp),max(timestamp) FROM intraday").fetchall())
        print(db.sql("SELECT status,count(*),sum(bars) FROM minute_audit GROUP BY 1").fetchall())

