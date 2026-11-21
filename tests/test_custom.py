import json,time
from datetime import date
import pandas as pd
import pytest
from fastapi.testclient import TestClient
import custom_api as api
from historical import connect,build
from minute_archive import schema,store_bars
from kp_engine import IST
from private_demo.gate import SessionGate,COOKIE

@pytest.fixture
def client(tmp_path,monkeypatch):
    path=tmp_path/'research.duckdb'
    with connect(path) as con:
        schema(con)
        times=pd.date_range('2026-11-19 10:00',periods=5,freq='15min',tz=IST)
        list(build(con,times))
        stamps=pd.date_range(times[0],periods=121,freq='min')
        bars=pd.DataFrame({'timestamp':stamps,'open':100.,'high':102.,'low':99.,'close':101.})
        store_bars(con,bars,'Synthetic test fixture','test','fixture','close',1)
    monkeypatch.setattr(api,'DB',path)
    return TestClient(api.app)

def test_calculation_and_input_validation(client):
    body={'timestamp':'2026-11-20T10:30:00+05:30'}
    result=client.post('/api/calculate',json=body)
    assert result.status_code==200
    assert len(result.json()['rows'])==9
    assert len(result.json()['ruling_planets'])==5
    assert client.post('/api/calculate',json={'timestamp':'2026-11-20T10:30:00'}).status_code==422
    assert client.post('/api/calculate',json=body,headers={'Origin':'https://evil.test'}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.test'}).status_code==400
    assert client.get('/api/coverage').status_code==200
    assert client.get('/api/timeline?day=2026-11-20&step=15').status_code==200

@pytest.mark.parametrize('mode',['exact','partial','sign','nakshatra','sub','score','longitude'])
def test_matches_order_pagination_and_outcomes(client,mode):
    body={'timestamp':'2026-11-19T11:00:00+05:30','start':'2026-11-19','end':'2026-11-19','mode':mode,'tolerance':180,'minimum':-100,'maximum':100,'factors':['day'],'limit':2}
    response=client.post('/api/matches',json=body)
    assert response.status_code==200,response.text
    rows=response.json()['rows']
    assert all(pd.Timestamp(r['timestamp'])<pd.Timestamp(body['timestamp']) for r in rows)
    assert len(rows)<=2
    for r in rows:assert r['return_5']==0 and r['price_60']==101
    if response.json()['total']>2:
        page=client.post('/api/matches',json={**body,'offset':2}).json()['rows']
        assert not {r['timestamp'] for r in rows}&{r['timestamp'] for r in page}
    stats=client.post('/api/statistics',json=body).json()
    assert stats['with_data']==response.json()['total']

def test_missing_and_aggregation(client):
    result=client.get('/api/candles',params={'timestamp':'2000-01-01T10:30:00+05:30'})
    assert result.json()['rows']==[]
    result=client.get('/api/candles',params={'timestamp':'2026-11-19T10:30:00+05:30','interval':5})
    assert len(result.json()['rows'])==24
    with api.db() as con:
        with pytest.raises(Exception,match='read-only'):con.execute('delete from snapshots')

def test_gate_permissions_expiry_and_feedback(client,tmp_path,monkeypatch):
    import private_demo.install_connector as install
    monkeypatch.setattr(install,'HOME',tmp_path)
    gate=SessionGate(api.app,'test-only-random-password',time.time()+60,'https://testserver')
    c=TestClient(gate,base_url='https://testserver',headers={'x-forwarded-proto':'https'})
    assert c.get('/api/health').status_code==401
    assert c.post('/login',data={'password':'wrong'},headers={'Origin':'https://testserver'}).status_code==401
    response=c.post('/login',data={'password':'test-only-random-password'},headers={'Origin':'https://testserver'},follow_redirects=False)
    assert response.status_code==303
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    assert c.get('/api/health').status_code==200
    for path in ['/api/admin/jobs','/api/admin/feedback','/api/admin/diagnostics','/api/admin/sync','/api/backtest']:
        assert c.get(path).status_code==403
        assert c.post(path,json={},headers={'Origin':'https://testserver'}).status_code==403
    for path in ['/archive/research.duckdb','/custom_api.py','/.env','/api/unknown']:
        assert c.get(path).status_code==404
    assert c.post('/api/calculate',json={'timestamp':'2026-11-20T10:30:00+05:30'},headers={'Origin':'https://evil.test'}).status_code==403
    response=c.post('/api/feedback',json={'page':'Test','timestamp':'test','expected':'expected','actual':'actual','comments':'x'*1800},headers={'Origin':'https://testserver'})
    assert response.status_code==200,response.text
    assert (tmp_path/'custom-feedback.sqlite3').exists()
    assert c.get('/api/health').headers['cache-control']=='no-store, private'
    gate.expires=time.time()-1
    assert c.get('/api/health').status_code==410

def test_upstox_retries_identity_and_secret(monkeypatch):
    import upstox_history as u
    from types import SimpleNamespace
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=429 if len(calls)==1 else 200,headers={'Retry-After':'0'},json=lambda:{'status':'success','data':{'candles':[]}})
    monkeypatch.setattr(u.requests,'get',get)
    monkeypatch.setattr(u.time,'sleep',lambda n:None)
    assert u.fetch('not-a-real-token',date(2026,1,1),date(2026,1,28))['status']=='success'
    assert len(calls)==2 and 'NSE_INDEX%7CNifty%2050/minutes/1' in calls[0]
    assert all('not-a-real-token' not in url for url in calls)
    monkeypatch.setenv('UPSTOX_ACCESS_TOKEN','fixture-token')
    assert api.broker_status()=={'configured':True,'instrument':'NSE_INDEX|Nifty 50'}

def test_tunnel_monitor_expiry_and_stop(monkeypatch):
    import private_demo.session as session
    import io
    class Child:
        returncode=None
        def __init__(self,*args,**kwargs):self.stdout=io.StringIO('https://local-fixture.trycloudflare.com\n');self.terminated=False
        def __enter__(self):children.append(self);return self
        def __exit__(self,*args):pass
        def poll(self):return self.returncode
        def terminate(self):self.terminated=True;self.returncode=0
        def wait(self,**kwargs):return 0
    children=[]
    monkeypatch.setattr(session.subprocess,'Popen',Child)
    for expire in (True,False):
        gate=SessionGate(api.app,'test-only-password',time.time()+(.15 if expire else 30),'http://127.0.0.1:1')
        gate.token_hash=b'fixture'
        start=time.monotonic()
        session.monitor(['mock-connector'],gate,lambda:False if expire else time.monotonic()-start>.15,'fixture',show=lambda value:None)
        assert gate.expires==0 and gate.token_hash is None and children[-1].terminated

def test_upstox_checkpoint_resume(tmp_path,monkeypatch):
    import upstox_history as u,historical
    path=tmp_path/'broker.duckdb'
    real_connect=connect
    with real_connect(path) as con:schema(con)
    monkeypatch.setattr(historical,'connect',lambda:real_connect(path))
    monkeypatch.setattr(u,'RAW',tmp_path)
    monkeypatch.setattr(u,'verify_instrument',lambda:{'instrument_key':u.KEY})
    calls=[]
    def fetch(secret,start,end,current=False):
        calls.append((start,end,current))
        if len(calls)==2:raise ValueError('fixture connection failure')
        return {'data':{'candles':[[str(pd.Timestamp(start,tz=IST)+pd.Timedelta(hours=10)),100,102,99,101,0,0]]}}
    monkeypatch.setattr(u,'fetch',fetch)
    with pytest.raises(ValueError):list(u.sync_minutes('fixture',date(2026,1,1),date(2026,2,5),None))
    assert (calls[0][1]-calls[0][0]).days==27
    assert len(list(u.sync_minutes('fixture',date(2026,1,1),date(2026,2,5),None)))==1
    with real_connect(path) as con:assert con.execute('select count(*) from intraday').fetchall()[0][0]==2
    assert list(u.sync_minutes('fixture',date(2026,1,1),date(2026,2,5),None))==[]

def test_daily_provider_preserves_existing_and_resumes(tmp_path,monkeypatch):
    import upstox_daily as d
    from historical import insert_daily
    path=tmp_path/'daily.duckdb'
    with connect(path) as con:insert_daily(con,[('NIFTY 50',date(2024,1,1),100.,102.,99.,101.,'NSE','fixture','fixture')])
    monkeypatch.setattr(d,'connect',lambda:connect(path))
    monkeypatch.setattr(d,'RAW',tmp_path)
    monkeypatch.setattr(d,'verify_instrument',lambda:None)
    calls=[]
    def fetch(*args,**kwargs):
        calls.append(kwargs)
        return {'data':{'candles':[['2024-01-01T00:00:00+05:30',100,103,99,102],['2024-01-02T00:00:00+05:30',100,103,99,102]]}}
    monkeypatch.setattr(d,'fetch',fetch)
    list(d.sync_daily('fixture',date(2024,1,1),date(2024,1,2)))
    assert calls==[{'unit':'days'}]
    assert list(d.sync_daily('fixture',date(2024,1,1),date(2024,1,2)))==[]
    with connect(path) as con:
        assert con.execute('select close from daily order by day').fetchall()==[(101.,),(102.,)]
        assert con.execute('select count(*) from broker_daily_conflicts').fetchall()==[(1,)]
