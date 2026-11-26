from pathlib import Path
from datetime import datetime,date
import pytest
from kp_engine import KPChart,IST
def test_nov25_workbook_actual_outputs():
    import openpyxl
    path=Path.home()/'Downloads/Excel Based Nifty/Intraday Astrology - Full Day 2026-11-25 102028.xlsm'
    if not path.exists():pytest.skip('New workbook unavailable')
    w=openpyxl.load_workbook(path,read_only=True,data_only=True)
    rows=list(w['FullDay_Analysis'].values)[1:]
    assert len(rows)==26
    for r in rows:
        t=datetime.combine(date(2026,11,25),r[0]).replace(tzinfo=IST)
        c=KPChart(t).calculate()
        assert list(c['ruling_planets'].values())==list(r[1:6])
        assert list(c['components'].values())==list(r[13:20])
        assert c['kp_score']==r[20]
