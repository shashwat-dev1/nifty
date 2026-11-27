from pathlib import Path
import pytest
from tests.test_custom import client

def test_production_no_fabrication():
    root=Path(__file__).resolve().parents[1]/'web'
    source='\n'.join(p.read_text(encoding='utf-8-sig') for p in root.glob('*.tsx'))
    for fabricated in ['24,852.15','51,320.40','85.7%','4.82','High Alpha Confidence','Forward Predictive Drift: +1.43','17369.25','points15={48.6}','88.4% HIGH DIVERGENCE']:
        assert fabricated not in source
    assert 'stats?.average_points' in source
    assert '/api/market' in source

def test_neutral_denominators(client):
    body={'timestamp':'2026-11-19T11:00:00+05:30','start':'2026-11-19','end':'2026-11-19','mode':'score','minimum':-100,'maximum':100,'neutral':.05}
    r=client.post('/api/statistics',json=body).json()
    assert r['positive']+r['negative']+r['flat']==r['complete_forward_windows']
    assert r['positive_percent']+r['negative_percent']+r['neutral_percent']==pytest.approx(100)
    assert r['flat']==r['complete_forward_windows']
    assert r['with_data']+r['without_data']==r['matches']

@pytest.mark.parametrize('mode',['pada','star','similarity'])
def test_restored_match_modes(client,mode):
    body={'timestamp':'2026-11-19T11:00:00+05:30','start':'2026-11-19','end':'2026-11-19','mode':mode,'similarity':0}
    r=client.post('/api/matches',json=body)
    assert r.status_code==200,r.text
    if mode=='similarity':assert all(0<=x['similarity']<=100 for x in r.json()['rows'])


def test_summary_all_matches_signed_averages_medians_and_missing_windows(client):
    import custom_api as api
    from datetime import datetime
    with api.db(write=True) as con:
        for stamp,price in [('10:15',111),('10:30',91),('10:45',91)]:
            con.execute('update intraday set close=? where timestamp=?',[price,datetime.fromisoformat('2026-11-19T'+stamp+':00+05:30')])
    body={'timestamp':'2026-11-19T11:00:00+05:30','start':'2026-11-19','end':'2026-11-19','mode':'partial','factors':['day'],'horizon':15,'limit':1}
    page=client.post('/api/matches',json=body).json()
    assert len(page['rows'])==1 and page['total']==4
    stats=client.post('/api/statistics',json=body).json()
    assert stats['matches']==4 and stats['complete_forward_windows']==4
    assert (stats['positive'],stats['negative'],stats['flat'])==(2,1,1)
    assert (stats['positive_percent'],stats['negative_percent'],stats['neutral_percent'])==(50,25,25)
    assert stats['average_positive_points']==stats['median_positive_points']==10
    assert stats['average_negative_points']==stats['median_negative_points']==-20
    assert stats['average_points']==0 and stats['median_points']==5
    with api.db(write=True) as con:
        con.execute("delete from intraday where timestamp='2026-11-19T10:52:00+05:30'")
    stats=client.post('/api/statistics',json=body).json()
    assert stats['matches']==stats['with_data']==4
    assert stats['complete_forward_windows']==3 and stats['incomplete_forward_windows']==1
    assert (stats['positive'],stats['negative'],stats['flat'])==(1,1,1)
    assert stats['average_points']==pytest.approx(-10/3)
    assert stats['median_points']==0
