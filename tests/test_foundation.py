from datetime import date,datetime,timedelta,timezone
import pytest
from kp_engine import day_lord,KPChart,sub_lord,normalize_time
from kp_diagnostics import subdivision

@pytest.mark.parametrize('offset,expected',enumerate(['Moon','Mars','Mercury','Jupiter','Venus','Saturn','Sun']))
def test_civil_weekday(offset,expected):
    assert day_lord(date(2026,11,16)+timedelta(days=offset))==expected

def test_ist_day_boundary():
    before=datetime(2026,11,19,18,29,59,tzinfo=timezone.utc)
    after=before+timedelta(seconds=1)
    assert day_lord(normalize_time(before).date())=='Jupiter'
    assert day_lord(normalize_time(after).date())=='Venus'
    assert KPChart(after).calculate()['ruling_planets']['day']=='Venus'

def test_independent_first_nakshatra_sub_boundaries():
    # Ashwini: Ketu 7/120 and Venus 20/120 of 13 1/3 degrees.
    boundary=(40/3)*(7/120)
    assert sub_lord(boundary-1e-9)=='Ketu'
    assert sub_lord(boundary+1e-9)=='Venus'
    value=subdivision(boundary+1e-9)
    assert value['sub_start_degrees']==pytest.approx(7/9)
    assert value['sub_end_degrees']==pytest.approx(3)
    assert subdivision(360)['sub_lord']=='Ketu'
