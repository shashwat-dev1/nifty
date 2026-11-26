from datetime import date
import json
import full_day_archive as a
def test_exact_entire_day_and_order(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'ROOT',tmp_path)
    day,rows,sig,canonical=a.calculate(date(2026,11,25))
    assert len(rows)==26 and rows[0][1]=='09:15' and rows[-1][1]=='15:30'
    assert rows[0][2:7]==['Mercury','Venus','Moon','Saturn','Jupiter']
    with a.connection() as con:
        con.execute('insert into days values(?,?,?,?)',['2000-01-01',sig,canonical,json.dumps(rows)])
        con.execute('insert into days values(?,?,?,?)',['2000-01-02',sig,canonical+'changed',json.dumps(rows)])
    assert a.search(date(2026,11,25))['matches']==['2000-01-01']

def test_majority_counts_and_ties():
    _,rows,_,_=a.calculate(date(2026,11,25))
    result=a.majority(rows)
    assert result['day_lord']['values']==['Mercury']
    assert result['day_lord']['slots']==26
    assert sum(result['score_direction_counts'].values())==26
    two=[list(rows[0]),list(rows[1])]
    two[0][5]='Saturn';two[1][5]='Mercury'
    assert a.majority(two)['moon_sub_lord']['values']==['Mercury','Saturn']

def test_same_negative_bias_is_not_same_kp_majority():
    _,today,_,_=a.calculate(date(2026,11,25))
    _,yesterday,_,_=a.calculate(date(2026,11,24))
    first=a.majority(today);second=a.majority(yesterday)
    assert a.majority_key(first)!=a.majority_key(second)
    assert first['day_lord']['values']==['Mercury']
    assert second['day_lord']['values']==['Mars']

def test_soft_matching_requires_lords_not_just_score_bias():
    _,rows,_,_=a.calculate(date(2026,11,25));selected=a.majority(rows)
    import copy
    other=copy.deepcopy(selected)
    for k in a.LORDS:other[k]['values']=['Different']
    assert a.soft_comparison(selected,other) is None
    for k in a.LORDS[:3]:other[k]=copy.deepcopy(selected[k])
    result=a.soft_comparison(selected,other)
    assert result['lords_agree']==3
    assert result['similarity_percent']==66
    assert result['different_factors']=='moon_sub_lord, lagna_lord'
    assert a.soft_comparison(selected,selected)['similarity_percent']==100

def test_relaxed_search_uses_only_earlier_days(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'ROOT',tmp_path)
    _,rows,sig,canonical=a.calculate(date(2026,11,25))
    with a.connection() as con:
        for d in ['2026-11-24','2026-11-25','2026-11-26']:
            con.execute('insert into days values(?,?,?,?)',[d,sig,canonical,json.dumps(rows)])
    result=a.search(date(2026,11,25))
    assert [r['matching_date'] for r in result['soft_matches']]==['2026-11-24']
    assert result['soft_match_count']==1

def test_exact_slot_matches_any_time_and_all_six_fields(tmp_path,monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(a,'ROOT',tmp_path)
    _,rows,sig,canonical=a.calculate(date(2026,11,25))
    chosen=list(rows[0]);chosen[1]='14:45'
    wrong=list(chosen);wrong[14]+=1
    with a.connection() as con:
        con.execute('insert into days values(?,?,?,?)',['2025-10-25',sig,canonical,json.dumps([chosen,wrong[:1]+['15:00']+wrong[2:]])])
    result=a.slot_search(datetime.fromisoformat('2026-11-25T09:15:00+05:30'))
    assert result['total']==1
    assert result['rows'][0]['timestamp']=='2025-10-25T14:45:00+05:30'
    assert result['rows'][0]['kp_score']==10
    assert result['rows'][0]['moon_sub_lord']=='Saturn'

def test_slot_api_joins_complete_candles_and_rejects_gaps(monkeypatch):
    import custom_api as api
    import duckdb,copy
    from datetime import datetime,timedelta
    from fastapi.testclient import TestClient
    t=datetime.fromisoformat('2023-01-04T09:15:00+05:30')
    monkeypatch.setattr(a,'slot_search',lambda stamp:{'rows':[{'timestamp':t.isoformat(),**dict(zip(a.LORDS,api.KPChart(t).calculate()['ruling_planets'].values())),'kp_score':api.KPChart(t).calculate()['kp_score']}],'total':1})
    missing=False
    def fixture_db():
        con=duckdb.connect(':memory:')
        con.execute("SET TimeZone='Asia/Kolkata'")
        con.execute('CREATE TABLE intraday(timestamp TIMESTAMPTZ,open DOUBLE,close DOUBLE,interval_minutes INTEGER)')
        for i in range(1,16):
            if missing and i==7:continue
            con.execute('INSERT INTO intraday VALUES(?,?,?,1)',[t+timedelta(minutes=i),100+i,101+i])
        return con
    monkeypatch.setattr(api,'db',fixture_db)
    client=TestClient(api.app)
    params={'timestamp':'2026-11-25T12:15:00+05:30'}
    r=client.get('/api/kp/slot-matches',params=params)
    assert r.status_code==200
    row=r.json()['rows'][0]
    assert (row['slot_open'],row['slot_close'],row['market_data'])==(101,116,'Complete')
    missing=True
    row=client.get('/api/kp/slot-matches',params=params).json()['rows'][0]
    assert row['minute_candles']==14 and row['market_data']=='Incomplete'
    assert row['slot_open'] is None and row['slot_close'] is None
    assert client.get('/api/kp/slot-matches',params={'timestamp':'2026-11-25T12:15:00'}).status_code==422

def test_exact_six_rejects_same_lords_with_different_score():
    import custom_api as api
    import duckdb,copy
    from datetime import datetime
    t=datetime.fromisoformat('2026-11-25T12:15:00+05:30')
    detail=api.KPChart(t).calculate();other=copy.deepcopy(detail);other['kp_score']+=1
    con=duckdb.connect(':memory:')
    con.execute('CREATE TABLE snapshots(ts TIMESTAMPTZ,model TEXT,lat DOUBLE,lon DOUBLE,details TEXT)')
    for ts,d in [('2025-01-01T10:00:00+05:30',detail),('2025-01-02T10:00:00+05:30',other)]:
        con.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)',[ts,api.MODEL,api.LAT,api.LON,json.dumps(d)])
    body=api.Search(timestamp=t,start=date(2025,1,1),end=date(2025,1,3),mode='exact_score')
    count,rows,_=api.search_rows(con,body)
    assert count==1 and json.loads(rows.iloc[0].details)['kp_score']==detail['kp_score']
    body.mode='exact'
    assert api.search_rows(con,body)[0]==2
    con.close()


def test_screenshot_is_april_first_not_january_four():
    # User screenshot: all 26 KP scores and five lords, read in row order.
    scores=[18,14,18,18,18,18,18,-6,2,-6,-6,-1,-1,-1,-1,-2,14,2,2,2,2,2,2,-2,-2,11]
    _,april,_,_=a.calculate(date(2023,4,1))
    assert [r[14] for r in april]==scores
    for i,r in enumerate(april):
        assert r[2:5]==['Saturn','Moon','Mercury']
        assert r[5]==('Venus' if i<11 else 'Sun' if i<16 else 'Moon' if i<25 else 'Mars')
        assert r[6]==('Venus' if i<6 else 'Mercury' if i<15 else 'Moon' if i<24 else 'Sun')
    _,january,_,_=a.calculate(date(2023,1,4))
    _,today,_,_=a.calculate(date(2026,11,25))
    assert january[3][2:7]+[january[3][14]]==today[13][2:7]+[today[13][14]]
    assert january[4][2:7]+[january[4][14]]==today[13][2:7]+[today[13][14]]
    assert january[0][2]=='Mercury' and april[0][2]=='Saturn'


def test_corrupt_slot_archive_is_blocked(monkeypatch):
    import custom_api as api
    from fastapi.testclient import TestClient
    monkeypatch.setattr(a,'slot_search',lambda t:{'rows':[{'timestamp':'2023-01-04T10:15:00+05:30','day_lord':'Saturn'}],'total':1})
    r=TestClient(api.app).get('/api/kp/slot-matches',params={'timestamp':'2026-11-25T12:30:00+05:30'})
    assert r.status_code==409
    assert 'fresh KP verification' in r.json()['detail']
