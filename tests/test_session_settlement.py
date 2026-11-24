import pandas as pd
from historical import connect
from minute_archive import schema,store_bars
import paper_service
from session_settlement import session_prices
def test_special_session_complete_and_missing(tmp_path,monkeypatch):
    monkeypatch.setattr('session_settlement.calendar',lambda day:{'status':'verified trading','open':'18:00','close':'18:03','source':'isolated synthetic fixture'})
    with connect(tmp_path/'fixture.db') as con:
        schema(con)
        stamps=pd.date_range('2025-11-01 18:01',periods=3,freq='min',tz='Asia/Kolkata')
        bars=pd.DataFrame({'timestamp':stamps,'open':100.,'high':102.,'low':99.,'close':[100.,101.,102.]})
        store_bars(con,bars,'isolated synthetic fixture','test','test','close',1)
        p={'timestamp':'2025-11-01T17:00:00+05:30','horizon':'premarket_full_day','reference':99}
        result=session_prices(con,p)
        assert result[:2]==(100.,102.)
        con.execute('delete from intraday where timestamp=?',[stamps[1]])
        assert session_prices(con,p) is None
def test_unknown_schedule_blocks(tmp_path,monkeypatch):
    monkeypatch.setattr('session_settlement.calendar',lambda day:{'status':'unverified'})
    with connect(tmp_path/'fixture.db') as con:
        assert session_prices(con,{'timestamp':'2025-11-01T09:30:00+05:30','horizon':'next_session'}) is None
