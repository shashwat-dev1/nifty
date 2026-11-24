"""Resumable, versioned feature rebuild from genuine stored candle timestamps."""
import argparse,json
from pathlib import Path
from historical import connect,build,MODEL
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--step',type=int,choices=[1,5,15,30],default=15);args=p.parse_args()
    with connect() as con:
        times=con.sql('select timestamp from intraday where interval_minutes=1 order by timestamp').df().timestamp
    times=times[(times.dt.hour*60+times.dt.minute)%args.step==0]
    progress=Path('archive/market-index-progress.json')
    for i in range(0,len(times),128):
        with connect() as con:list(build(con,times.iloc[i:i+128]))
        progress.write_text(json.dumps({'model':MODEL,'step':args.step,'processed':min(i+128,len(times)),'eligible':len(times),'status':'running'}))
    with connect() as con:
        report=con.execute('select count(*),min(ts),max(ts) from snapshots where model=? and ts in (select timestamp from intraday)',[MODEL]).fetchall()[0]
    progress.write_text(json.dumps({'model':MODEL,'step':args.step,'processed':len(times),'eligible':len(times),'status':'complete','actual_index':list(map(str,report))}))
    print(progress.read_text())
