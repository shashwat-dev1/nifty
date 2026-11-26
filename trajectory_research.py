"""Genuine multi-output minute trajectories; fixed 2023 fit/2024 calibration/2025 replay."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from historical import connect,MODEL
OUT=Path(__file__).parent/'archive/trajectory'
def train():
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import StandardScaler,OneHotEncoder
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    import skops.io as sio
    OUT.mkdir(exist_ok=True);metrics=[];records=[]
    with connect() as con:bars=con.sql('select timestamp,close,source from intraday where interval_minutes=1 order by timestamp').df().set_index('timestamp')
    version=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    for h in [15,30,60,120,240]:
        d=pd.read_parquet(f'archive/movement-v2/dataset-{h}.parquet')
        # Exact per-minute joins; reject absent minute or any cross-date path.
        stamps=pd.DatetimeIndex(d.timestamp);ref=bars.close.reindex(stamps).to_numpy()
        future=np.column_stack([bars.close.reindex(stamps+pd.Timedelta(minutes=k)).to_numpy() for k in range(1,h+1)])
        valid=np.isfinite(future).all(1)&np.isfinite(ref)&(stamps.date==(stamps+pd.Timedelta(minutes=h)).date)
        d=d.loc[valid].reset_index(drop=True);ref=ref[valid];y=100*(future[valid]/ref[:,None]-1)
        # Non-overlapping decisions for evaluation; fitting may overlap within prior years.
        fit=np.flatnonzero(d.timestamp.dt.year<2024);cal=np.flatnonzero(d.timestamp.dt.year==2024)
        test=[];end=None
        for i,t in enumerate(d.timestamp):
            if t.year==2025 and (end is None or t>=end):test.append(i);end=t+pd.Timedelta(minutes=h)
        test=np.array(test)
        if min(len(fit),len(cal),len(test))<30:continue
        market=['momentum','volatility','hour','weekday'];cats=['day','moon_sign','moon_star','moon_sub','lagna']
        kp=[c for c in d if c not in market+['timestamp','label_end','return_pct','points','close']]
        fit_cutoff=str(d.iloc[fit].label_end.max());cal_cutoff=str(d.iloc[cal].label_end.max())
        predictions={}
        for name,cols in [('zero',market),('trend',market),('market',market),('kp',kp),('combined',market+kp)]:
            if name=='zero':pred=np.zeros_like(y[test]);calpred=np.zeros_like(y[cal])
            elif name=='trend':
                pred=np.clip(d.momentum.to_numpy()[test,None]*100/15*np.arange(1,h+1),-10,10);calpred=np.clip(d.momentum.to_numpy()[cal,None]*100/15*np.arange(1,h+1),-10,10)
            else:
                pre=ColumnTransformer([('categories',OneHotEncoder(handle_unknown='ignore',sparse_output=False),[c for c in cols if c in cats]),('numeric',StandardScaler(),[c for c in cols if c not in cats])])
                model=make_pipeline(pre,Ridge(alpha=100));model.fit(d.iloc[fit][cols],y[fit]);pred=model.predict(d.iloc[test][cols]);calpred=model.predict(d.iloc[cal][cols])
                path=OUT/f'{name}-{h}.skops';sio.dump(model,path);unknown=sio.get_untrusted_types(file=path)
                if any(not t.startswith(('sklearn.','numpy.','scipy.')) for t in unknown):raise ValueError('Unexpected artifact type')
                assert np.allclose(sio.load(path,trusted=unknown).predict(d.iloc[test[:3]][cols]),pred[:3],atol=1e-10)
                path.with_suffix('.json').write_text(json.dumps({'features':cols,'fit_cutoff':fit_cutoff,'calibration_cutoff':cal_cutoff,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'version':version,'kp_version':MODEL,'format':'skops multi-output ridge; exact minute return outputs'},indent=2))
            residual=y[cal]-calpred;lo,hi=np.quantile(residual,[.05,.95],axis=0)
            predictions[name]=(pred,pred+lo,pred+hi)
        # Independent categorical analog: equal-weight exact five lords; otherwise
        # same Moon star/sub. Only fit-period paths, all completed before decisions.
        analog=[];lower=[];upper=[];samples=[]
        values={c:d[c].to_numpy() for c in cats}
        fitvalues={c:values[c][fit] for c in cats}
        for i in test:
            mask=np.ones(len(fit),bool)
            for c in cats:mask&=(fitvalues[c]==values[c][i])
            if mask.sum()<5:mask=(fitvalues['moon_star']==values['moon_star'][i])&(fitvalues['moon_sub']==values['moon_sub'][i])
            selected=y[fit[mask]];samples.append(len(selected))
            if len(selected)<5:analog.append(np.full(h,np.nan));lower.append(np.full(h,np.nan));upper.append(np.full(h,np.nan))
            else:analog.append(np.median(selected,axis=0));lower.append(np.quantile(selected,.05,axis=0));upper.append(np.quantile(selected,.95,axis=0))
        predictions['analog']=(np.array(analog),np.array(lower),np.array(upper))
        for name,(pred,lo,hi) in predictions.items():
            valid=np.isfinite(pred).all(1);actual=y[test];error=(pred-actual)*ref[test,None]/100
            per=np.mean(abs(error),axis=1);days=d.iloc[test].timestamp.dt.date.to_numpy();daily=pd.DataFrame({'day':days[valid],'error':per[valid]}).groupby('day').error.agg(['sum','count']).to_numpy();rng=np.random.default_rng(42)
            sums=daily[rng.integers(0,len(daily),size=(1000,len(daily)))].sum(1);ci=np.quantile(sums[:,0]/sums[:,1],[.025,.975])
            metrics.append({'model':name,'horizon':h,'year':2025,'n':int(valid.sum()),'days':len(daily),'path_mae':float(np.nanmean(per)),'path_mae_day_ci95':ci.tolist(),'endpoint_mae':float(np.nanmean(abs(error[:,-1]))),'path_rmse':float(np.sqrt(np.nanmean(error**2))),'pointwise_coverage':float(np.mean(((actual>=lo)&(actual<=hi))[valid])),'whole_path_coverage':float(np.mean(((actual>=lo)&(actual<=hi)).all(1)[valid])),'band':'pointwise chronological residual 5/95 quantiles; analog empirical quantiles, not calibrated guarantee'})
            for j,i in enumerate(test):
                if not valid[j]:continue
                records.append({'timestamp':str(d.timestamp.iat[i]),'horizon':h,'model':name,'version':version,'reference':float(ref[i]),'predicted_returns':pred[j].tolist(),'lower_returns':lo[j].tolist(),'upper_returns':hi[j].tolist(),'actual_returns':actual[j].tolist(),'analog_n':samples[j] if name=='analog' else None,'fit_cutoff':fit_cutoff,'calibration_cutoff':cal_cutoff})
        (OUT/'metrics.json').write_text(json.dumps(metrics,indent=2));pd.DataFrame(records).to_parquet(OUT/'paths.parquet',index=False)
    print('Trajectory evaluations:',len(metrics))
if __name__=='__main__':train()
