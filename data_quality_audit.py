"""Database-backed provenance audit; absent exchange evidence remains uncertain."""
import json
from pathlib import Path
from historical import connect,MODEL
def audit():
    with connect() as con:
        rows=con.sql("select source,count(*) records,min(timestamp)::varchar first,max(timestamp)::varchar last,count(distinct timestamp::date) session_count,sum(case when open<=0 or low<=0 or high<greatest(open,close,low) or low>least(open,close) then 1 else 0 end) invalid_ohlc,count(*)-count(distinct timestamp) duplicates from intraday group by source").df()
        sessions=con.sql("select timestamp::date::varchar AS session_day,source,count(*) bars,min(timestamp)::varchar first,max(timestamp)::varchar last from intraday group by all order by session_day").df()
        missing=con.sql("select day::varchar AS session_day from daily where instrument='NIFTY 50' and day between (select min(timestamp)::date from intraday) and (select max(timestamp)::date from intraday) and day not in(select distinct timestamp::date from intraday)").df()
        kp=con.execute('select count(*),min(ts)::varchar,max(ts)::varchar from snapshots where model=? and ts in(select timestamp from intraday)',[MODEL]).fetchall()[0]
        conflicts=con.sql('select count(*) n from broker_conflicts').fetchall()[0][0]
    report={'instrument':'NIFTY 50 spot index as labelled by source; broker master independently verified; third-party identity remains provenance review','timezone':'Stored TIMESTAMPTZ; provider minute starts shifted to closes','sources':json.loads(rows.to_json(orient='records')),'sessions':json.loads(sessions.to_json(orient='records')),'missing_daily_sessions':missing.session_day.tolist(),'indexed_market_features':list(kp),'broker_price_conflicts':conflicts,'calendar_evidence':'Only explicitly sourced dates verified; all other dates uncertain for prospective scheduling','classification':'OHLC/duplicate checks confirm internal consistency only; source/session certification remains uncertain'}
    Path('DATA_QUALITY_REPORT.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':print('Audited sources:',len(audit()['sources']))
