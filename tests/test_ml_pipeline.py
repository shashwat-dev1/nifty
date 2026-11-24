import pandas as pd
from historical import connect,build
from minute_archive import schema,store_bars
from kp_engine import IST
from ml_research import dataset

def test_features_do_not_change_with_future_prices(tmp_path):
    with connect(tmp_path/'test.duckdb') as con:
        schema(con)
        stamps=pd.date_range('2026-01-05 09:16',periods=120,freq='min',tz=IST)
        bars=pd.DataFrame({'timestamp':stamps,'open':100.,'high':102.,'low':99.,'close':[100+i*.001 for i in range(120)]})
        store_bars(con,bars,'test fixture','fixture','test','close',1)
        list(build(con,stamps[30::15]))
        before=dataset(con,15)
        cutoff=stamps[75]
        con.execute('update intraday set close=close+1 where timestamp>?',[cutoff])
        after=dataset(con,15)
        cols=[c for c in before if c not in ['return_pct','label_end']]
        pd.testing.assert_frame_equal(before[before.timestamp<=cutoff][cols].reset_index(drop=True),after[after.timestamp<=cutoff][cols].reset_index(drop=True))
