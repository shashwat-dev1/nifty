import pandas as pd
import pytest
from historical_forecast import forecast,ROOT
def test_saved_endpoint_matches_independent_candles():
    if not (ROOT/'predictions.parquet').exists():pytest.skip('Research data not installed')
    f=forecast('2025-11-19T10:00:00+05:30','market',60)
    assert f['status']=='available'
    assert pd.Timestamp(f['fit_cutoff'])<pd.Timestamp(f['timestamp'])
    assert pd.Timestamp(f['calibration_cutoff'])<pd.Timestamp(f['timestamp'])
    assert f['path'] is None or len(f['path']['points'])==60
    assert f['predicted_endpoint']==pytest.approx(f['reference']+f['expected_points'])
    assert f['actual_endpoint']-f['reference']==pytest.approx(f['actual_points'])
    assert f['absolute_error']==pytest.approx(abs(f['expected_points']-f['actual_points']))
def test_missing_and_analog_never_fabricate_path():
    assert forecast('2000-01-01T10:00:00+05:30')['status']=='unavailable'
    assert forecast('2000-01-01T10:00:00+05:30','analog')['path'] is None
