from pathlib import Path
import pandas as pd
import numpy as np
import pytest
from historical_forecast import forecast
def test_path_is_multistep_and_time_aligned():
    root=Path('archive/trajectory')
    if not (root/'paths.parquet').exists():pytest.skip('Trajectory research not installed')
    d=pd.read_parquet(root/'paths.parquet');r=d[(d.model=='market')&(d.horizon==15)].iloc[0]
    f=forecast(r.timestamp,'market',15)
    assert f['path'] is not None
    pts=f['path']['points'];t=pd.Timestamp(r.timestamp)
    assert [pd.Timestamp(p['timestamp']) for p in pts]==[t+pd.Timedelta(minutes=k) for k in range(1,16)]
    np.testing.assert_allclose([p['predicted'] for p in pts],r.reference*(1+np.asarray(r.predicted_returns)/100))
    assert f['path_error']==pytest.approx(np.mean([abs(p['difference']) for p in pts]))
    assert pd.Timestamp(r.fit_cutoff)<t and pd.Timestamp(r.calibration_cutoff)<t
