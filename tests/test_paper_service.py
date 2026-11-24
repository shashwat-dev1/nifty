import json
from datetime import datetime,timezone,timedelta
import pytest
import paper_service as paper
from prediction_log import connection
def test_missing_artifact_blocks_live_recording(tmp_path):
    assert 'frozen artifact missing' in paper.eligibility({})
    with pytest.raises(ValueError,match='Model blocked'):paper.record_generated({}, {}, {}, '09:30',tmp_path/'paper.db')
def test_idempotency_and_stale_guard(tmp_path,monkeypatch):
    import hashlib
    artifact=tmp_path/'model';artifact.write_bytes(b'explicit test fixture')
    model={**dict.fromkeys(paper.CHECKS,True),'version':'fixture','artifact':str(artifact),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'training_cutoff':'2020-01-01T00:00:00+00:00','horizon':15}
    monkeypatch.setattr(paper,'calendar',lambda day:{'status':'verified trading','source':'test fixture'})
    now=datetime.now(timezone.utc);obs={'timestamp':now.isoformat(),'price':100.,'source':'test fixture'}
    out={'probabilities':[.3,.3,.4],'lower_points':-2,'median_points':0,'upper_points':2,'expected_points':0}
    path=tmp_path/'paper.db'
    a=paper.record_generated(model,obs,out,'09:30',path,now)
    assert paper.record_generated(model,obs,out,'09:30',path,now)==a
    with connection(path) as con:assert con.execute('select count(*) from events').fetchone()[0]==1
    with pytest.raises(ValueError,match='Stale'):paper.record_generated(model,obs,out,'10:00',path,now+timedelta(minutes=3))
