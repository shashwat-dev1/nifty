import pytest
from bundle_runtime import infer
def test_bundle_rejects_foreign_path(tmp_path):
    with pytest.raises(ValueError,match='registered root'):infer({'artifact':str(tmp_path/'foreign.skops')},{})
def test_registered_bundle_schema_and_reload():
    from bundle_runtime import models
    from pathlib import Path
    if not Path('archive/movement-v2').exists():pytest.skip('Research artifacts not installed')
    m=next(m for m in models() if m['target']=='15' and m['model']=='market')
    with pytest.raises(ValueError,match='schema'):infer(m,{})
    values={k:0. for k in m['features']}
    a=infer(m,values);b=infer(m,values)
    assert a==b and sum(a['probabilities'])==pytest.approx(1)
