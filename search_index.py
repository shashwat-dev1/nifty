"""Bounded-memory lookup derived from authoritative snapshot records."""
FACTORS=('day','moon_sign','moon_star','moon_sub','lagna')
def build(con):
    con.execute('SET preserve_insertion_order=false')
    fields=','.join('CAST(NULL AS VARCHAR) AS match_'+k for k in FACTORS)
    con.execute('CREATE OR REPLACE TABLE snapshot_match_index AS SELECT ts,model,lat,lon,'+fields+',CAST(NULL AS DOUBLE) AS match_score FROM snapshots WHERE false')
    paths=["$.ruling_planets."+k for k in FACTORS]+['$.kp_score']
    values=','.join('v['+str(i+1)+']' for i in range(5))+',CAST(v[6] AS DOUBLE)'
    maximum=con.execute('select max(rowid) from snapshots').fetchone()[0]
    for start in range(0,(maximum or 0)+1,256):
        con.execute('INSERT INTO snapshot_match_index WITH parsed AS MATERIALIZED (SELECT ts,model,lat,lon,json_extract_string(details,?) v FROM snapshots WHERE rowid>=? AND rowid<?) SELECT ts,model,lat,lon,'+values+' FROM parsed',[paths,start,start+256])
    con.execute('CREATE INDEX IF NOT EXISTS snapshot_match_time ON snapshot_match_index(model,ts)')
    source=con.execute('select count(*) from snapshots').fetchone()[0]
    if con.execute('select count(*) from snapshot_match_index').fetchone()[0]!=source:raise ValueError('Incomplete derived lookup')
