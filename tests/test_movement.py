import pandas as pd
import numpy as np
from historical import connect,insert_daily
from movement_models import make_dataset
def test_premarket_inputs_do_not_use_current_open(tmp_path):
    with connect(tmp_path/'test.db') as con:
        days=pd.bdate_range('2023-01-02',periods=45)
        rows=[('NIFTY 50',t.date(),100+i,102+i,99+i,101+i,'test fixture','fixture','fixture') for i,t in enumerate(days)]
        insert_daily(con,rows)
        first=make_dataset(con,'premarket_full_day')
        selected=first.iloc[-1].timestamp.date()
        con.execute("update daily set open=open+5 where day=?",[selected])
        second=make_dataset(con,'premarket_full_day')
        features=[c for c in first if c not in ['points','return_pct']]
        pd.testing.assert_frame_equal(first[features],second[features])
        assert first.iloc[-1].points!=second.iloc[-1].points
        assert first.iloc[-1].timestamp.hour==9
