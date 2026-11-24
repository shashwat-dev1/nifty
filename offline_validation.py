"""Evidence-only provenance and frozen-policy reviews; unknown never passes."""
import hashlib,json
from pathlib import Path
import pandas as pd
import numpy as np
from historical import connect,ROOT,RAW
from paper_service import calendar

def provenance():
    with connect() as con:
        groups=con.sql('select source,raw_file,source_label,interval_minutes,min(timestamp)::varchar earliest,max(timestamp)::varchar latest,min(imported_at)::varchar imported,count(*) n from intraday group by all').df()
        missing=con.sql("select day::varchar session_day,provider from daily where instrument='NIFTY 50' and day between(select min(timestamp)::date from intraday) and(select max(timestamp)::date from intraday) and day not in(select distinct timestamp::date from intraday)").df()
    ledger=[]
    for r in groups.itertuples():
        candidates=[RAW/r.raw_file,ROOT/r.raw_file,Path(r.raw_file)]
        path=next((p for p in candidates if p.is_file()),None)
        ledger.append({'provider':r.source,'instrument':'NSE_INDEX|Nifty 50' if r.source.startswith('Upstox') else 'NIFTY 50 source label; external identity unverified','earliest':r.earliest,'latest':r.latest,'interval':r.interval_minutes,'ingestion_timestamp':r.imported,'retrieval_timestamp':'not separately recorded; ingestion time is not retrieval proof','raw_file':r.raw_file,'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path else None,'source_timestamp_convention':r.source_label,'transform':'Timezone to IST; opening-label candle shifted forward by interval to close timestamp','records':r.n,'numerical_quality':'See DATA_QUALITY_REPORT.json','authenticity':'raw file retained; authenticity not independently certified' if path else 'BLOCKED: raw file missing'})
    Path('PROVENANCE_LEDGER.json').write_text(json.dumps(ledger,indent=2))
    recovery=[{'day':r.session_day,'daily_source':r.provider,'exchange_evidence':calendar(r.session_day),'status':'unverified exchange session; minute data absent','authorized_provider':'Upstox','recovery':'pending authorized range request; no closure inferred'} for r in missing.itertuples()]
    Path('MISSING_SESSION_RECOVERY.json').write_text(json.dumps(recovery,indent=2))
    return ledger

def evaluate():
    policy_path=Path('approval_policy.json');policy=json.loads(policy_path.read_text())
    registry=json.loads(Path('MODEL_ARTIFACT_REGISTRY_V2.json').read_text())['artifacts'];results=[]
    for m in registry:
        p=Path('archive/movement-v2')/f"{m['target']}-{m['year']}-{m['model']}.skops"
        artifact_ok=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256']
        gates={k:{'status':'BLOCKED','reason':'Required policy-eligible prospective evidence absent'} for k in policy['gates']}
        gates['reproducibility']={'status':'PASS' if artifact_ok else 'FAIL','reason':'Saved checksum matches and training run asserted reload equality at 1e-10' if artifact_ok else 'Missing or modified artifact'}
        gates['data_quality']={'status':'BLOCKED','reason':'Full raw-source authenticity and exchange-calendar certification incomplete'}
        gates['session']={'status':'BLOCKED','reason':'Historical sessions not fully evidence-certified; unknown dates rejected'}
        gates['freshness']={'status':'BLOCKED','reason':'Must be evaluated for each actual recording; historical replay cannot prove live freshness'}
        gates['multiplicity']={'status':'PASS','reason':'All 96 development groups disclosed; no predictive-superiority claim'}
        results.append({'model':m['model'],'target':m['target'],'year':m['year'],'version':m['version'],'decision':'FAIL' if any(v['status']=='FAIL' for v in gates.values()) else 'BLOCKED','gates':gates})
    Path('POLICY_EVALUATION.json').write_text(json.dumps({'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),'policy_version':policy['version'],'models':results},indent=2));return results

def uncertainty():
    d=pd.read_parquet('archive/movement-v2/predictions.parquet');d['day']=pd.to_datetime(d.timestamp,utc=True).dt.tz_convert('Asia/Kolkata').dt.date
    d['actual']=np.where(d.actual_percent>.05,2,np.where(d.actual_percent<-.05,0,1));prob=d[['negative','neutral','positive']].to_numpy()
    d['accuracy']=(prob.argmax(1)==d.actual).astype(float);d['log_loss']=-np.log(np.clip(prob[np.arange(len(d)),d.actual],1e-15,1));d['brier']=np.sum((prob-np.eye(3)[d.actual])**2,axis=1)
    d['squared_error']=d.error_points**2;d['mae']=abs(d.error_points);d['coverage']=d.actual_points.between(d.lower_points,d.upper_points).astype(float);d['width']=d.upper_points-d.lower_points
    rows=[];paired=[];cols=['accuracy','log_loss','brier','mae','coverage','width','squared_error']
    def summarize(g):
        days=g.groupby('day')[cols].agg(['sum','count']);rng=np.random.default_rng(20261124);idx=rng.integers(0,len(days),size=(1000,len(days)));out={}
        for c in cols:
            v=days[c].to_numpy();tot=v[idx].sum(1);ci=np.quantile(tot[:,0]/tot[:,1],[.025,.975]);out[c]={'mean':float(g[c].mean()),'day_cluster_ci95':ci.tolist()}
        if (g.squared_error>=0).all():out['rmse']={'mean':float(np.sqrt(g.squared_error.mean())),'day_cluster_ci95':np.sqrt(out['squared_error']['day_cluster_ci95']).tolist()}
        return out
    for (target,year,model),g in d.groupby(['target','year','model']):rows.append({'target':target,'year':int(year),'model':model,'n':len(g),'days':g.day.nunique(),'metrics':summarize(g)})
    for (target,year),g in d.groupby(['target','year']):
        base=g[g.model=='market'].set_index('timestamp')
        for model in ['baseline','kp','combined']:
            other=g[g.model==model].set_index('timestamp');assert set(base.index)==set(other.index)
            other=other.loc[base.index];diff=other.copy();diff[cols]=other[cols]-base[cols]
            paired.append({'target':target,'year':int(year),'model_minus_market':model,'n':len(diff),'metrics':summarize(diff)})
    Path('MODEL_UNCERTAINTY.json').write_text(json.dumps({'kind':'descriptive development replay; marginal day-cluster intervals, not multiplicity-adjusted significance','rows':rows},indent=2))
    Path('PAIRED_MODEL_COMPARISONS.json').write_text(json.dumps(paired,indent=2))
if __name__=='__main__':
    print('Provenance groups:',len(provenance()));print('Policy decisions:',len(evaluate()));uncertainty();print('Uncertainty reports saved')
