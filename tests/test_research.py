from datetime import date
import pandas as pd
import pytest
from research import prepare,save,read,events,evaluate
from kp_engine import KPChart,IST
from datetime import datetime

def candles():
    raw=pd.DataFrame({"timestamp":pd.date_range("2026-11-19 09:15",periods=7,freq="5min"),"close":range(100,107)})
    return prepare(raw,{c:c for c in raw},"Asia/Kolkata",5,False,False)

def test_atomic_import(tmp_path):
    path=tmp_path/"test.db"
    bars=candles()
    save(bars,"sample",path)
    save(bars,"sample",path)
    bars.loc[3,"close"]=400
    with pytest.raises(ValueError): save(bars,"other",path)
    assert list(read(path).close)==list(range(100,107))

def test_window_selection(tmp_path):
    path=tmp_path/"test.db"
    save(candles(),"fixture",path)
    bars=read(path)
    assert len(events(bars,15))==2
    assert len(events(bars,15,nonoverlap=False))==4
    assert events(bars.iloc[:2],15).empty

def test_minimum_counts_dates():
    df=pd.DataFrame({"date":[date(2026,1,i) for i in [1,1,2]],"timestamp":[1,2,3],"score":[1]*3,"return_pct":[1,2,-1],"outcome":[1,1,-1]})
    assert evaluate(df,date(2026,1,2),["score"],2,0).empty
    result=evaluate(df,date(2026,1,2),["score"],1,10)
    assert result.net_pct.iloc[0]==pytest.approx(-1.1)

def test_moon_reference():
    assert KPChart(datetime(2026,11,20,9,15,tzinfo=IST)).longitude("Moon")==pytest.approx(334.5977195,abs=.001)

