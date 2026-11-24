import sqlite3
from datetime import datetime,timezone,timedelta
import pytest
from prediction_log import record_forecast,connection
def test_prospective_rejects_replay_and_unvalidated(tmp_path):
    now=datetime.now(timezone.utc)
    p={'timestamp':(now+timedelta(minutes=1)).isoformat(),'input_timestamp':now.isoformat(),'probabilities':[.3,.3,.4],'validation_status':'research only'}
    with pytest.raises(ValueError,match='approved'):record_forecast(p,tmp_path/'log.db')
    p['validation_status']='approved prospective'
    key=record_forecast(p,tmp_path/'log.db')
    with connection(tmp_path/'log.db') as con:
        with pytest.raises(sqlite3.IntegrityError,match='append only'):con.execute('delete from events')
    p['timestamp']=(now-timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError,match='predate'):record_forecast(p,tmp_path/'log.db')
