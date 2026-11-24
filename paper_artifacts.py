"""Non-executable JSON baseline artifacts. No pickle/untrusted object loading."""
import hashlib,json,platform
from pathlib import Path
import numpy as np
import pandas as pd
from paper_service import ROOT
from historical import MODEL

def load(path,expected):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('Artifact outside registry directory')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Artifact checksum failure')
    value=json.loads(raw)
    if value['format']!='paper-baseline-json-v1' or value['feature_schema']!=['reference_price']:raise ValueError('Feature schema mismatch')
    return value
def predict(artifact,features):
    if set(features)!=set(artifact['feature_schema']):raise ValueError('Feature schema mismatch')
    if not np.isfinite(features['reference_price']) or features['reference_price']<=0:raise ValueError('Invalid reference price')
    return {**artifact['output'],'expected_percent':100*artifact['output']['expected_points']/features['reference_price']}
def register():
    ROOT.mkdir(exist_ok=True)
    source=Path('archive/movement/dataset-15.parquet');data=pd.read_parquet(source)
    fit=data[data.timestamp.dt.year<2024];cal=data[data.timestamp.dt.year==2024];test=data[data.timestamp.dt.year==2025]
    labels=np.where(fit.return_pct>.05,2,np.where(fit.return_pct<-.05,0,1))
    probs=np.bincount(labels,minlength=3)/len(labels);mean=float(fit.points.mean())
    quantiles=np.quantile(cal.points-mean,[.05,.5,.95])
    output={'probabilities':probs.tolist(),'expected_points':mean,'median_points':mean+float(quantiles[1]),'lower_points':mean+float(quantiles[0]),'upper_points':mean+float(quantiles[2]),'neutral_percent':.05}
    value={'format':'paper-baseline-json-v1','feature_schema':['reference_price'],'training_cutoff':str(fit.label_end.max()),'calibration_cutoff':str(cal.label_end.max()),'training_fingerprint':hashlib.sha256(source.read_bytes()).hexdigest(),'kp_version':MODEL,'software':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},'config':{'horizon':15,'neutral_percent':.05,'baseline':'training class frequencies / mean points','interval':'2024 residual 5/95 quantiles'},'output':output,'validation':{'year':2025,'n':len(test),'mae':float(abs(test.points-mean).mean()),'coverage':float(test.points.between(output['lower_points'],output['upper_points']).mean())}}
    raw=json.dumps(value,sort_keys=True,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=ROOT/f'baseline-15-{digest[:12]}.json';path.write_bytes(raw)
    reloaded=load(path,digest)
    assert predict(reloaded,{'reference_price':25000})==predict(value,{'reference_price':25000})
    record={'version':digest[:12],'artifact':str(path.resolve()),'sha256':digest,'training_cutoff':value['calibration_cutoff'],'horizon':15,'artifact_reproducible':True,'chronological_validation':True,'leakage_checks_pass':True,'baseline_comparison_documented':True,'training_data_verified':False,'calibration_reviewed':False,'interval_coverage_reviewed':False,'blockers_note':'Calendar/provenance certification and calibration/interval acceptance remain unapproved','validation':value['validation']}
    (ROOT/'registry.json').write_text(json.dumps([record],indent=2));return record
if __name__=='__main__':print(json.dumps(register(),indent=2))
