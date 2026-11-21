"""Seed the archive from a checked-out PowerNSE index_closes tree and export snapshots."""
from datetime import date,timedelta
from time import perf_counter
import pandas as pd
from historical import connect,import_bundle,sync,build,ROOT,IST

def refresh():
    with connect() as db:
        import_bundle(db,ROOT/"source/nse-data/raw/index_closes")
        last=db.execute("select max(day) from trading_dates").fetchone()[0]
        if last is None:raise ValueError("Missing PowerNSE source tree")
        end=pd.Timestamp.now(tz=IST).date()-timedelta(days=1)
        for res in sync(db,last,end):print(res,flush=True)
        dates=pd.DatetimeIndex(db.sql("select day from trading_dates order by day").df().day).tz_localize(IST)
        start=perf_counter()
        stamps=[dates,dates+pd.Timedelta(hours=9,minutes=15),dates+pd.Timedelta(hours=10,minutes=30)]
        if db.execute("select count(*) from information_schema.tables where table_name='intraday'").fetchall()[0][0]:
            stamps.append(pd.DatetimeIndex(db.sql("SELECT timestamp FROM intraday WHERE minute(timestamp)%15=0 ORDER BY timestamp").df().timestamp))
        for stamp in stamps:
            for done,total in build(db,stamp):pass
        print("Feature generation seconds",perf_counter()-start,flush=True)
        for table in ["daily","snapshots"]:
            db.execute(f"COPY {table} TO '{(ROOT/(table+'.parquet')).as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        print(db.sql("select instrument,count(*),min(day),max(day) from daily group by 1").fetchall())
if __name__=="__main__":refresh()

