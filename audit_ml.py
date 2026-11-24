"""Recompute published metrics and day-cluster uncertainty from saved predictions."""
import json
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss,balanced_accuracy_score,confusion_matrix
from ml_research import OUT
def audit():
    data=pd.read_parquet(OUT/'predictions.parquet')
    data['stamp']=pd.to_datetime(data.timestamp,utc=True).dt.tz_convert('Asia/Kolkata')
    data['year']=data.stamp.dt.year;data['day']=data.stamp.dt.date
    published=json.loads((OUT/'metrics.json').read_text());rows=[]
    for (h,y),group in data.groupby(['horizon','year']):
        expected=None
        for name,g in group.groupby('model'):
            keys=g.timestamp.tolist()
            if expected is None:expected=keys
            assert keys==expected,'Models evaluated on different timestamps'
            assert not g.timestamp.duplicated().any()
            labels=np.where(g.return_percent>.05,2,np.where(g.return_percent<-.05,0,1))
            assert np.array_equal(labels,g.actual)
            stamps=g.stamp.sort_values()
            assert (stamps.diff().dropna()>=pd.Timedelta(minutes=int(h))).all()
            probs=g[['negative','neutral','positive']].to_numpy()
            assert np.allclose(probs.sum(axis=1),1)
            accuracy=float((g.prediction==g.actual).mean())
            loss=float(log_loss(g.actual,probs,labels=[0,1,2]))
            report=next(m for m in published if m['horizon']==h and m['year']==y and m['model']==name)
            assert abs(report['accuracy']-accuracy)<1e-12 and abs(report['log_loss']-loss)<1e-12
            # Resample whole trading days, preserving dependence within each day.
            daily=g.assign(correct=g.prediction.eq(g.actual).astype(int)).groupby('day').correct.agg(['sum','count']).to_numpy()
            rng=np.random.default_rng(20261124);draws=rng.integers(0,len(daily),size=(1000,len(daily)))
            totals=daily[draws].sum(axis=1);boot=totals[:,0]/totals[:,1]
            rows.append(dict(horizon=int(h),year=int(y),model=name,n=len(g),trading_days=len(daily),class_counts=g.actual.value_counts().to_dict(),accuracy=accuracy,accuracy_day_cluster_ci95=np.quantile(boot,[.025,.975]).tolist(),log_loss=loss,brier=float(np.mean(np.sum((probs-np.eye(3)[g.actual])**2,axis=1))),balanced_accuracy=float(balanced_accuracy_score(g.actual,g.prediction)),confusion=confusion_matrix(g.actual,g.prediction,labels=[0,1,2]).tolist()))
    (OUT/'audit.json').write_text(json.dumps({'status':'saved metrics reconciled','method':'1000 whole-day bootstrap replicates; marginal intervals, not simultaneous multiple-comparison significance','rows':rows},indent=2))
    return rows
if __name__=='__main__':print('Audited model/year/horizon groups:',len(audit()))
