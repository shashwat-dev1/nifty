import json,hashlib
import pytest
from paper_artifacts import load,predict
def test_safe_json_artifact_checks(tmp_path,monkeypatch):
    import paper_artifacts as a
    monkeypatch.setattr(a,'ROOT',tmp_path)
    p=tmp_path/'artifact.json';v={'format':'paper-baseline-json-v1','feature_schema':['reference_price'],'output':{'expected_points':1}}
    p.write_text(json.dumps(v));digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert predict(load(p,digest),{'reference_price':100})['expected_percent']==1
    with pytest.raises(ValueError,match='schema'):predict(v,{'other':1})
    p.write_text('{}')
    with pytest.raises(ValueError,match='checksum'):load(p,digest)
def test_scheduler_remains_blocked_without_approved_artifact(tmp_path,monkeypatch):
    import paper_scheduler as s
    state={'enabled':True,'windows':['09:30']}
    monkeypatch.setattr(s,'config',lambda:state.copy())
    monkeypatch.setattr(s,'registry',lambda:[])
    monkeypatch.setattr(s,'save',lambda value:state.update(value))
    s.tick()
    assert state['last_status']=='blocked: no approved model artifact'
