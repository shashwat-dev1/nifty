"""Smoke-test the desktop navigation against an isolated offline warehouse."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
import historical
import archive_ui

def test_all_pages_offline(tmp_path,monkeypatch):
    real_connect=historical.connect
    new_connect=lambda:real_connect(tmp_path/"local.duckdb")
    monkeypatch.setattr(historical,"connect",new_connect)
    monkeypatch.setattr(archive_ui,"connect",new_connect)
    monkeypatch.setattr(archive_ui,"ROOT",tmp_path)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/"dashboard.py"),default_timeout=30).run()
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception and not app.error,page

