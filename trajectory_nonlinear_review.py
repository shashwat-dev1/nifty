"""One fixed nonlinear candidate; development-only 2024 evaluation, no 2025/26 tuning."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.pipeline import make_pipeline
from historical import connect
def run():
    d=pd.read_parquet('archive/movement-v2/dataset-60.parquet')
    with connect() as con:bars=con.sql('select timestamp,close from intraday where interval_minutes=1').df().set_index('timestamp').close
    t=pd.DatetimeIndex(d.timestamp);ref=bars.reindex(t).to_numpy();future=np.column_stack([bars.reindex(t+pd.Timedelta(minutes=k)).to_numpy() for k in range(1,61)])
    valid=np.isfinite(future).all(1)&(t.date==(t+pd.Timedelta(minutes=60)).date)&(t.year<=2024)
    d=d[valid].reset_index(drop=True);y=100*(future[valid]/ref[valid,None]-1);ref=ref[valid]
    fit=np.flatnonzero(d.timestamp.dt.year<2024);test=[];end=None
    for i,t in enumerate(d.timestamp):
        if t.year==2024 and (end is None or t>=end):test.append(i);end=t+pd.Timedelta(minutes=60)
    test=np.array(test);market=['momentum','volatility','hour','weekday'];cats=['day','moon_sign','moon_star','moon_sub','lagna'];kp=[c for c in d if c not in market+['timestamp','label_end','return_pct','points','close']];results=[]
    for name,cols in [('market',market),('kp',kp),('combined',market+kp)]:
        pre=ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),[c for c in cols if c in cats]),('num','passthrough',[c for c in cols if c not in cats])])
        model=make_pipeline(pre,ExtraTreesRegressor(n_estimators=64,max_depth=8,min_samples_leaf=50,random_state=24,n_jobs=4))
        model.fit(d.iloc[fit][cols],y[fit]);pred=model.predict(d.iloc[test][cols]);error=(pred-y[test])*ref[test,None]/100
        results.append({'model':name,'evaluation':'2024 development only; fixed candidate, no 2025/2026 tuning','n':len(test),'path_mae':float(abs(error).mean()),'endpoint_mae':float(abs(error[:,-1]).mean()),'zero_path_mae':float((abs(y[test])*ref[test,None]/100).mean()),'deployed':False})
    Path('NONLINEAR_MODEL_REVIEW.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
if __name__=='__main__':run()
