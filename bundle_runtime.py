"""Trusted-local skops runtime with manifest/schema checks; no baseline fallback."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).parent/'archive/movement-v2'
def models():
    rows=[]
    for path in ROOT.glob('*.json'):
        if path.name=='metrics.json':continue
        m=json.loads(path.read_text());artifact=path.with_suffix('.skops')
        rows.append({**m,'artifact':str(artifact),'training_cutoff':m['calibration_cutoff'],'horizon':int(m['target']) if m['target'].isdigit() else m['target'],'runtime':'skops','runtime_id':artifact.stem})
    return rows
def infer(model,features):
    import skops.io as sio
    path=Path(model['artifact']).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('Artifact outside registered root')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=model['sha256']:raise ValueError('Artifact checksum mismatch')
    if set(features)!=set(model['features']):raise ValueError('Feature schema mismatch')
    frame=pd.DataFrame([{k:features[k] for k in model['features']}])
    unknown=sio.get_untrusted_types(file=path)
    if any(not v.startswith(('sklearn.','numpy.','scipy.')) for v in unknown):raise ValueError('Untrusted artifact type')
    bundle=sio.load(path,trusted=unknown)
    raw=bundle['classifier'].predict_proba(frame)[0];p=np.zeros(3)
    for i,c in enumerate(bundle['classifier'].classes_):p[int(c)]=raw[i]
    mean=float(bundle['regressor'].predict(frame)[0]);lo,med,hi=model['residual_quantiles']
    return {'probabilities':p.tolist(),'expected_points':mean,'median_points':mean+med,'lower_points':mean+lo,'upper_points':mean+hi,'neutral_percent':model['neutral_percent']}
def live_features(model,observation):
    from historical import detailed,connect
    t=pd.Timestamp(observation['timestamp']);d=json.loads(detailed(t))
    with connect() as con:
        bars=con.execute("select timestamp,close from intraday where interval_minutes=1 and timestamp between ? and ? order by timestamp",[t-pd.Timedelta(minutes=30),t]).df()
    if len(bars)!=31 or not bars.timestamp.diff().dropna().eq(pd.Timedelta(minutes=1)).all() or bars.timestamp.dt.date.nunique()!=1:raise ValueError('Incomplete input lookback')
    f={'momentum':bars.close.iloc[-1]/bars.close.iloc[-16]-1,'volatility':bars.close.pct_change().dropna().std(),'hour':t.hour+t.minute/60,'weekday':t.weekday(),'score':d['kp_score'],**d['ruling_planets'],**d['components']}
    for planet,v in d['positions'].items():f[planet+'_sin']=np.sin(np.deg2rad(v['longitude']));f[planet+'_cos']=np.cos(np.deg2rad(v['longitude']))
    if not set(model['features'])<=set(f):raise ValueError('Live feature contract unsupported for this target')
    return {k:f[k] for k in model['features']}
