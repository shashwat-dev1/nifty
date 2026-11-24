"""Versioned direction/point research, development years only; no 2026 retuning."""
import hashlib,json,argparse,os
import numpy as np
import pandas as pd
from pathlib import Path
from historical import connect,MODEL,detailed
from kp_engine import IST
from ml_research import dataset
OUT=Path(__file__).parent/os.getenv('NIFTY_MOVEMENT_OUTPUT','archive/movement')

def make_dataset(con,target):
    if target in ('remaining_session','next_session'):
        d=make_dataset(con,'15')
        bars=con.sql('select timestamp,open,close from intraday where interval_minutes=1 order by timestamp').df()
        groups={day:g for day,g in bars.groupby(bars.timestamp.dt.date)}
        official=[r[0] for r in con.sql("select day from daily where instrument='NIFTY 50' order by day").fetchall()]
        rows=[]
        for r in d.to_dict('records'):
            day=r['timestamp'].date();g=groups.get(day)
            if target=='next_session':
                following=next((v for v in official if v>day),None);g=groups.get(following)
            if g is None or len(g)!=375 or g.timestamp.iloc[0].strftime('%H:%M')!='09:16' or g.timestamp.iloc[-1].strftime('%H:%M')!='15:30':continue
            if not g.timestamp.diff().dropna().eq(pd.Timedelta(minutes=1)).all():continue
            reference=r['close'] if target=='remaining_session' else g.open.iloc[0]
            if g.timestamp.iloc[-1]<=r['timestamp']:continue
            r.update(points=g.close.iloc[-1]-reference,return_pct=100*(g.close.iloc[-1]/reference-1),label_end=g.timestamp.iloc[-1])
            rows.append(r)
        return pd.DataFrame(rows)
    if target.isdigit():
        h=int(target);d=dataset(con,h)
        ref=con.sql('select timestamp,close from intraday').df()
        d=d.merge(ref,on='timestamp')
        # Require uninterrupted input windows, not merely the preceding stored rows.
        valid=con.sql("select timestamp from (select timestamp,timestamp-lag(timestamp,30) over(partition by timestamp::date order by timestamp) span from intraday where interval_minutes=1) where span=interval '30 minutes'").df()
        d=d.merge(valid,on='timestamp');d['points']=d.close*d.return_pct/100
        return d
    prices=con.sql("select day,open,close from daily where instrument='NIFTY 50' order by day").df()
    prices['prior_return']=prices.close.pct_change().shift(1)
    prices['prior_vol']=prices.close.pct_change().rolling(20).std().shift(1)
    records=[]
    for i,r in enumerate(prices.itertuples()):
        if not np.isfinite(r.prior_return) or not np.isfinite(r.prior_vol):continue
        t=pd.Timestamp(r.day).tz_localize(IST)+pd.Timedelta(hours=9)
        kp=json.loads(detailed(t))
        record={'percent_reference':float(prices.close.iloc[i-1]),'timestamp':t,'label_end':t.normalize()+pd.Timedelta(hours=16),'momentum':r.prior_return,'volatility':r.prior_vol,'hour':9.,'weekday':t.weekday(),'score':kp['kp_score'],**kp['ruling_planets'],**kp['components']}
        if target=='premarket_full_day':
            if not np.isfinite(r.open) or r.open<=0:continue
            record.update(points=r.close-r.open,return_pct=100*(r.close/r.open-1))
        else:continue
        records.append(record)
    return pd.DataFrame(records)

def train(neutral=.05):
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression,Ridge,QuantileRegressor
    from sklearn.dummy import DummyClassifier,DummyRegressor
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator
    from sklearn.metrics import log_loss,mean_squared_error,mean_absolute_error
    OUT.mkdir(exist_ok=True)
    version=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    metrics=[];predictions=[]
    for target in ['15','30','60','120','240','premarket_full_day','remaining_session','next_session']:
        with connect() as con:d=make_dataset(con,target)
        if d.empty:continue
        d=d[d.timestamp.dt.year<=2025].copy()
        market=['momentum','volatility','hour','weekday'];cats=['day','moon_sign','moon_star','moon_sub','lagna']
        kp=[c for c in d if c not in market+['timestamp','label_end','return_pct','points','close','percent_reference']]
        d.to_parquet(OUT/f'dataset-{target}.parquet',index=False)
        for year in [2023,2024,2025]:
            start=pd.Timestamp(f'{year}-01-01',tz=IST);cal_start=start-pd.DateOffset(years=1)
            fit=d[d.label_end<cal_start-pd.Timedelta(days=1)]
            cal=d[(d.timestamp>=cal_start)&(d.label_end<start-pd.Timedelta(days=1))]
            test=d[d.timestamp.dt.year==year]
            # Non-overlapping test labels.
            chosen=[];last=None
            for r in test.itertuples():
                if last is None or r.timestamp>=last:chosen.append(r.Index);last=r.label_end
            test=test.loc[chosen]
            if min(len(fit),len(cal),len(test))<30:continue
            label=lambda x:np.where(x>neutral,2,np.where(x < -neutral,0,1))
            for name,cols in [('baseline',market),('market',market),('kp',kp),('combined',market+kp)]:
                def pre():return ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),[c for c in cols if c in cats]),('num',StandardScaler(),[c for c in cols if c not in cats])])
                classifier=make_pipeline(pre(),DummyClassifier(strategy='prior') if name=='baseline' else LogisticRegression(C=.1,max_iter=1000))
                classifier.fit(fit[cols],label(fit.return_pct))
                calibrated=CalibratedClassifierCV(FrozenEstimator(classifier),method='sigmoid')
                calibrated.fit(cal[cols],label(cal.return_pct));raw=calibrated.predict_proba(test[cols]);prob=np.zeros((len(test),3))
                for j,c in enumerate(calibrated.classes_):prob[:,int(c)]=raw[:,j]
                reg=make_pipeline(pre(),DummyRegressor() if name=='baseline' else Ridge(alpha=10))
                reg.fit(fit[cols],fit.points);mean=reg.predict(test[cols]);residual=cal.points-reg.predict(cal[cols])
                # Chronological residual quantiles; empirical coverage is measured, never guaranteed.
                lo,median,hi=np.quantile(residual,[.05,.5,.95]);actual=label(test.return_pct)
                if os.getenv('NIFTY_EXPORT_MODELS')=='1':
                    import skops.io as sio
                    import sklearn,platform
                    bundle={'classifier':calibrated,'regressor':reg}
                    artifact=OUT/f'{target}-{year}-{name}.skops'
                    sio.dump(bundle,artifact)
                    unknown=sio.get_untrusted_types(file=artifact)
                    # Only locally produced known sklearn/numpy types; never trust a foreign file.
                    if any(not kind.startswith(('sklearn.','numpy.','scipy.')) for kind in unknown):raise ValueError('Unexpected serialization type')
                    restored=sio.load(artifact,trusted=unknown)
                    assert np.allclose(restored['classifier'].predict_proba(test[cols]),raw,atol=1e-10,rtol=0)
                    assert np.allclose(restored['regressor'].predict(test[cols]),mean,atol=1e-10,rtol=0)
                    artifact.with_suffix('.json').write_text(json.dumps({'version':version,'target':target,'year':year,'model':name,'features':cols,'fit_cutoff':str(fit.label_end.max()),'calibration_cutoff':str(cal.label_end.max()),'training_fingerprint':hashlib.sha256(pd.util.hash_pandas_object(fit,index=True).values.tobytes()).hexdigest(),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'residual_quantiles':[float(lo),float(median),float(hi)],'neutral_percent':neutral,'software':{'python':platform.python_version(),'sklearn':sklearn.__version__,'numpy':np.__version__},'reload_tolerance':1e-10,'approval':'BLOCKED: development replay; frozen policy requires future prospective observations'},indent=2))
                metrics.append(dict(target=target,model=name,year=year,version=version,kp_version=MODEL,fit_rows=len(fit),calibration_rows=len(cal),test_rows=len(test),neutral_percent=neutral,accuracy=float((prob.argmax(1)==actual).mean()),log_loss=float(log_loss(actual,prob,labels=[0,1,2])),brier=float(np.mean(np.sum((prob-np.eye(3)[actual])**2,axis=1))),mae=float(mean_absolute_error(test.points,mean)),rmse=float(np.sqrt(mean_squared_error(test.points,mean))),interval_coverage=float(((test.points>=mean+lo)&(test.points<=mean+hi)).mean()),interval_method='chronological calibration residual 5/95 quantiles; no exchangeability guarantee'))
                for i,r in enumerate(test.itertuples()):predictions.append(dict(timestamp=str(r.timestamp),target=target,model=name,year=year,version=version,kind='development historical replay',negative=float(prob[i,0]),neutral=float(prob[i,1]),positive=float(prob[i,2]),expected_points=float(mean[i]),median_points=float(mean[i]+median),lower_points=float(mean[i]+lo),upper_points=float(mean[i]+hi),actual_points=r.points,error_points=float(mean[i]-r.points),actual_percent=r.return_pct,expected_percent=float(100*mean[i]/(getattr(r,'close',getattr(r,'percent_reference',np.nan)))),percent_reference_convention='current close for intraday; prior close for premarket estimate'))
        (OUT/'metrics.json').write_text(json.dumps(metrics,indent=2));pd.DataFrame(predictions).to_parquet(OUT/'predictions.parquet',index=False)
    return metrics
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--neutral',type=float,default=.05);a=p.parse_args();print(json.dumps(train(a.neutral),indent=2))
