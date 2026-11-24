import pytest
from quarantine import collect
def test_unknown_calendar_blocks_quarantine(monkeypatch):
    monkeypatch.setattr('quarantine.calendar',lambda d:{'status':'unverified'})
    with pytest.raises(ValueError,match='session hours'):collect({'horizon':15},{'timestamp':'2026-11-24T10:00:00+05:30'},'10:00')
def test_stale_data_blocks_quarantine(monkeypatch):
    monkeypatch.setattr('quarantine.calendar',lambda d:{'status':'verified trading','open':'09:15','close':'15:30'})
    with pytest.raises(ValueError,match='stale'):collect({'horizon':15},{'timestamp':'2026-11-24T10:00:00+05:30'},'10:00',now='2026-11-24T10:05:00+05:30')
