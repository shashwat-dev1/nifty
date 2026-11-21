from datetime import date,time
from pathlib import Path
import pandas as pd
import pytest
from historical import connect,parse_report,insert_daily,build,cached,daily_outcomes,walk_forward,sync
from minute_archive import schema,store_bars,attach_prices
from upstox_history import normalize
from kp_engine import IST

REPORT=b"Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value\nNifty 50,03/01/2024,100,103,99,101\nNifty 50 TRI,03/01/2024,200,210,180,205\n"

def test_spot_report_identity_and_conflict(tmp_path):
    day=date(2024,1,3)
    rows=parse_report(REPORT,day,"NSE","sample.csv")
    assert len(rows)==1
    with connect(tmp_path/"archive.db") as db:
        insert_daily(db,rows)
        insert_daily(db,rows)
        with pytest.raises(ValueError,match="conflict"):
            insert_daily(db,parse_report(REPORT.replace(b"99,101",b"99,102"),day,"NSE","other"))
        assert db.execute("select close from daily").fetchall()==[(101.,)]
    with pytest.raises(ValueError):parse_report(REPORT,date(2024,1,4),"NSE","wrong")

def test_resumable_features_without_prices(tmp_path):
    with connect(tmp_path/"archive.db") as db:
        stamps=pd.date_range("2026-11-20 09:15",periods=3,freq="15min",tz=IST)
        list(build(db,stamps[:1]))
        assert list(build(db,stamps))==[(2,2)]
        assert list(build(db,stamps))==[]
        frame=cached(db,stamps[0].date(),stamps[0].date(),decision=time(9,15))
        assert frame.score.tolist()==[18]
        assert db.execute("select count(*) from daily").fetchall()==[(0,)]

def test_report_checkpoint(tmp_path,monkeypatch):
    import historical
    monkeypatch.setattr(historical,"RAW",tmp_path)
    monkeypatch.setattr(historical,"ROOT",tmp_path)
    day=date(2024,1,3)
    (tmp_path/f"nse-{day}.csv").write_bytes(REPORT)
    monkeypatch.setattr(historical.requests,"get",lambda *a,**k:pytest.fail("cached file should be reused"))
    with connect(tmp_path/"archive.db") as db:
        assert list(sync(db,day,day))==[(day,"validated")]
        assert list(sync(db,day,day))==[(day,"validated")]

def test_intraday_gap_and_close_alignment(tmp_path):
    times=pd.date_range("2024-01-03 09:15",periods=5,freq="min",tz=IST)
    body={"data":{"candles":[[str(t),100,100,100,100,0,0] for t in times.delete(2)]}}
    bars=normalize(body,times[0].date(),times[0].date(),times[-1])
    assert list(bars.timestamp)==[times[1],times[2],times[4]]
    with connect(tmp_path/"archive.db") as db:
        schema(db)
        store_bars(db,bars,"test","fixture","test","start",1)
        assert attach_prices(db,bars.iloc[:1],1).exit_price.iat[0]==100
        assert pd.isna(attach_prices(db,bars.iloc[:1],3).exit_price.iat[0])

def test_purged_walk_forward_and_nonoverlap():
    days=pd.to_datetime(["2023-12-27","2023-12-28","2023-12-29","2024-01-02","2024-01-03","2024-01-04","2024-01-05"])
    frame=pd.DataFrame(dict(day=days,open=100.,close=[100,101,101,50,101,100,101],score=1))
    out=walk_forward(daily_outcomes(frame,2),"score",2,2024,2)
    assert out.training_n.tolist()==[2,2]
    assert out.prediction.tolist()==[1,1]
    assert out.day.tolist()==[days[3],days[5]]
    assert out.return_pct.iloc[0]==pytest.approx(1)

def test_original_workbook_when_available():
    book=next((Path.home()/"Downloads").glob("Intraday_Astrology*Updated_2.xlsm"),None)
    if not book:pytest.skip("Original workbook unavailable")
    from kp_engine import KPChart,slots
    excel=pytest.importorskip("openpyxl").load_workbook(book,read_only=True,data_only=True)
    rows=list(excel["FullDay_Analysis"].values)[1:27]
    assert len(rows)==26
    for ts,row in zip(slots(date(2026,11,20)),rows):
        result=KPChart(ts).calculate()
        assert list(result["components"].values())==list(row[13:20])
        assert list(result["ruling_planets"].values())==list(row[1:6])
        assert result["kp_score"]==row[20]


def test_signature_score_and_circular_filters():
    from types import SimpleNamespace
    from archive_ui import match_configurations
    from research import FACTORS
    chart=SimpleNamespace(longitude=lambda p:359.5 if p=="Moon" else 30.)
    kp={"ruling_planets":dict.fromkeys(FACTORS,"Sun"),"ruling_details":[{"class":"gain"}]*5,"majority":"bullish","components":{"B12":2}}
    rows=pd.DataFrame([{**dict.fromkeys(FACTORS,"Sun"),"score":1,"Moon":0.2,"Sun":30.4},
                       {**dict.fromkeys(FACTORS,"Sun"),"day":"Venus","score":-2,"Moon":120.,"Sun":90.}])
    assert list(match_configurations(rows,kp,chart,FACTORS).index)==[0]
    assert len(match_configurations(rows,kp,chart,["moon_star"]))==2
    assert list(match_configurations(rows,kp,chart,[],limits=(-3,0)).index)==[1]
    assert list(match_configurations(rows,kp,chart,[],selected=["Moon","Sun"],tol=1).index)==[0]
