"""Descriptive fixed input-only regime definitions, no selection on outcomes."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
def run():
    root=Path('archive/movement-v2');pred=pd.read_parquet(root/'predictions.parquet');reports=[]
    for target,g in pred.groupby('target'):
        d=pd.read_parquet(root/f'dataset-{target}.parquet')
        training=d[d.timestamp.dt.year<2023]
        vol=float(training.volatility.median());trend=float(training.momentum.abs().median())
        d['stamp']=d.timestamp.astype(str)
        merged=g.merge(d[['stamp','volatility','momentum','hour']],left_on='timestamp',right_on='stamp',validate='many_to_one')
        merged['day']=pd.to_datetime(merged.timestamp,utc=True).dt.tz_convert('Asia/Kolkata').dt.date
        merged['vol_regime']=np.where(merged.volatility>vol,'higher volatility','lower volatility')
        merged['trend_regime']=np.where(merged.momentum.abs()>trend,'higher prior momentum','lower prior momentum')
        merged['clock_regime']=np.where(merged.hour<11,'opening','midday/later')
        actual=np.where(merged.actual_percent>.05,2,np.where(merged.actual_percent<-.05,0,1));probs=merged[['negative','neutral','positive']].to_numpy()
        merged['correct']=(probs.argmax(1)==actual).astype(int)
        for regime in ['vol_regime','trend_regime','clock_regime']:
            for (model,year,value),r in merged.groupby(['model','year',regime]):
                daily=r.groupby('day').correct.agg(['sum','count']).to_numpy();rng=np.random.default_rng(42);v=daily[rng.integers(0,len(daily),size=(1000,len(daily)))].sum(1)
                reports.append({'target':target,'model':model,'year':int(year),'regime_definition':regime,'regime':value,'n':len(r),'days':len(daily),'accuracy':float(r.correct.mean()),'accuracy_day_ci95':np.quantile(v[:,0]/v[:,1],[.025,.975]).tolist(),'mae':float(abs(r.error_points).mean()),'volatility_threshold_from_pre2023':vol,'momentum_threshold_from_pre2023':trend})
    Path('REGIME_UNCERTAINTY.json').write_text(json.dumps({'purpose':'descriptive development replay; regimes not model selection or prospective approval','rows':reports},indent=2));print('Regime groups:',len(reports))
if __name__=='__main__':run()
