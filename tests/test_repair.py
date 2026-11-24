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
