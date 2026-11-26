"""Eligible saved endpoint forecasts anchored to actual observed prices; no invented path."""
import json
from pathlib import Path
from functools import lru_cache
import pandas as pd
import numpy as np
from historical import connect
from minute_archive import attach_prices
ROOT=Path(__file__).parent/'archive/movement-v2'
def trajectory(t,model,horizon):
    path=ROOT.parent/'trajectory/paths.parquet'
    if not path.exists():return None
    frame=pd.read_parquet(path);rows=frame[(pd.to_datetime(frame.timestamp,utc=True)==t)&(frame.model==model)&(frame.horizon==horizon)]
    if rows.empty:return None
    r=rows.iloc[0]
    if pd.Timestamp(r.fit_cutoff)>=t or pd.Timestamp(r.calibration_cutoff)>=t:return None
    ref=float(r.reference)
    return {'version':r.version,'fit_cutoff':r.fit_cutoff,'calibration_cutoff':r.calibration_cutoff,'kind':'2025 held-out multi-step path replay' if model!='analog' else '2025 held-out empirical KP analog trajectory','points':[{'timestamp':(t+pd.Timedelta(minutes=k)).isoformat(),'predicted':ref*(1+p/100),'lower':ref*(1+lo/100),'upper':ref*(1+hi/100),'actual':ref*(1+a/100),'difference':ref*(p-a)/100} for k,(p,lo,hi,a) in enumerate(zip(r.predicted_returns,r.lower_returns,r.upper_returns,r.actual_returns),1)],'reference':ref,'path_mae':float(np.mean(np.abs(np.array(r.predicted_returns)-np.array(r.actual_returns)))*ref/100),'sample_size':None if pd.isna(r.analog_n) else int(r.analog_n),'band':'Pointwise interval; not a whole-path guarantee'}
@lru_cache(maxsize=1)
def saved():return pd.read_parquet(ROOT/'predictions.parquet')
def forecast(timestamp,model='market',horizon=60):
    t=pd.Timestamp(timestamp)
    if t.tzinfo is None:raise ValueError('Timezone required')
    t=t.tz_convert('Asia/Kolkata')
    unavailable={'status':'unavailable','forecast_type':'endpoint only','path':None,'reason':'No eligible saved chronological prediction at this exact timestamp/model/horizon. No interpolation or future-trained substitute.'}
    path_forecast=trajectory(t,model,horizon)
    if path_forecast is not None:
        last=path_forecast['points'][-1];ref=path_forecast['reference'];actual=last['actual'];expected=last['predicted']
        return {'status':'available','forecast_type':path_forecast['kind'],'path':path_forecast,'path_note':path_forecast['band'],'path_error':path_forecast['path_mae'],'fit_cutoff':path_forecast['fit_cutoff'],'calibration_cutoff':path_forecast['calibration_cutoff'],'model':model,'version':path_forecast['version'],'reference':ref,'timestamp':t.isoformat(),'endpoint_timestamp':last['timestamp'],'predicted_endpoint':expected,'actual_endpoint':actual,'lower_endpoint':last['lower'],'upper_endpoint':last['upper'],'expected_points':expected-ref,'actual_points':actual-ref,'absolute_error':abs(expected-actual),'direction':'UP' if expected>ref else 'DOWN' if expected<ref else 'NEUTRAL','actual_direction':'UP' if actual>ref else 'DOWN' if actual<ref else 'NEUTRAL','direction_correct':(expected>=ref)==(actual>=ref),'interval_covered':last['lower']<=actual<=last['upper']}
    if model=='analog':return {**unavailable,'reason':'No chronologically validated analog path forecast is registered. Historical matches remain exploratory.'}
    if not (ROOT/'predictions.parquet').exists():return {**unavailable,'reason':'Saved forecast artifacts are not installed on this research server'}
    d=saved();mask=(pd.to_datetime(d.timestamp,utc=True)==t)&(d.model==model)&(d.target.astype(str)==str(horizon));rows=d[mask]
    if rows.empty:return unavailable
    row=rows.iloc[0];manifest=ROOT/f'{horizon}-{t.year}-{model}.json'
    if not manifest.exists():return unavailable
    meta=json.loads(manifest.read_text())
    if pd.Timestamp(meta['fit_cutoff'])>=t or pd.Timestamp(meta['calibration_cutoff'])>=t:return {**unavailable,'reason':'Model fit/calibration cutoff is not earlier than selected timestamp'}
    with connect() as con:
        out=attach_prices(con,pd.DataFrame({'timestamp':[t]}),horizon).iloc[0]
    if pd.isna(out.close):return {**unavailable,'reason':'Actual reference minute close is missing'}
    reference=float(out.close);end=t+pd.Timedelta(minutes=horizon);actual=None if pd.isna(out.exit_price) else float(out.exit_price)
    expected=reference+float(row.expected_points);lo=reference+float(row.lower_points);hi=reference+float(row.upper_points)
    actual_points=None if actual is None else actual-reference
    actual_class=None if actual is None else ('UP' if 100*actual_points/reference>.05 else 'DOWN' if 100*actual_points/reference<-.05 else 'NEUTRAL')
    probs={'DOWN':float(row.negative),'NEUTRAL':float(row.neutral),'UP':float(row.positive)};predicted=max(probs,key=probs.get)
    return {'status':'available','forecast_type':'saved chronological development out-of-sample endpoint','path':None,'path_error':None,'path_note':'No validated intrahorizon path model exists; endpoint and calibrated movement interval only.','timestamp':t.isoformat(),'endpoint_timestamp':end.isoformat(),'model':model,'version':row.version,'fit_cutoff':meta['fit_cutoff'],'calibration_cutoff':meta['calibration_cutoff'],'reference':reference,'predicted_endpoint':expected,'lower_endpoint':lo,'upper_endpoint':hi,'actual_endpoint':actual,'expected_points':float(row.expected_points),'actual_points':actual_points,'absolute_error':None if actual is None else abs(actual-expected),'direction':predicted,'actual_direction':actual_class,'direction_correct':None if actual is None else predicted==actual_class,'interval_covered':None if actual is None else lo<=actual<=hi,'probabilities':probs}
