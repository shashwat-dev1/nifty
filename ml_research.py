"""Fixed-protocol historical replay research. No prospective prediction claims."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from historical import connect,MODEL
from minute_archive import attach_prices

OUT=Path(__file__).parent/'archive/ml'
def dataset(con,horizon):
    frame=con.execute("select s.ts timestamp,s.details,i.close from snapshots s join intraday i on i.timestamp=s.ts where s.model=? and i.interval_minutes=1 order by s.ts",[MODEL]).df()
    frame=frame.drop_duplicates('timestamp')
    bars=con.sql('select timestamp,close from intraday where interval_minutes=1 order by timestamp').df().set_index('timestamp')
    grouped=bars.groupby(bars.index.date).close
    bars['momentum']=grouped.pct_change(15)
    bars['volatility']=grouped.transform(lambda s:s.pct_change().rolling(30,min_periods=30).std())
    frame=frame.merge(bars[['momentum','volatility']],left_on='timestamp',right_index=True)
    records=[]
    for row in frame.itertuples():
        d=json.loads(row.details)
        record={'timestamp':row.timestamp,'momentum':row.momentum,'volatility':row.volatility,'hour':row.timestamp.hour+row.timestamp.minute/60,'weekday':row.timestamp.weekday(),'score':d['kp_score']}
        record.update(d['ruling_planets']);record.update(d['components'])
        for p,v in d['positions'].items():
            record[p+'_sin']=np.sin(np.deg2rad(v['longitude']));record[p+'_cos']=np.cos(np.deg2rad(v['longitude']))
        records.append(record)
    result=pd.DataFrame(records)
    prices=attach_prices(con,result[['timestamp']],horizon)
    result['return_pct']=100*(prices.exit_price/prices.close-1)
    result['label_end']=result.timestamp+pd.Timedelta(minutes=horizon)
    return result.dropna().reset_index(drop=True)

def train(horizons=(15,30,60,120,240)):
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression
    from sklearn.dummy import DummyClassifier
    from sklearn.metrics import accuracy_score,balanced_accuracy_score,log_loss,confusion_matrix
    OUT.mkdir(exist_ok=True)
    version=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    summary=[];predictions=[]
    for h in horizons:
        with connect() as con:data=dataset(con,h)
        data.to_parquet(OUT/f'dataset-{h}.parquet',index=False)
        # Fixed annual expanding windows; 2026 is reserved final test, no tuning.
        market=['momentum','volatility','hour','weekday']
        cats=['day','moon_sign','moon_star','moon_sub','lagna']
        kp=[c for c in data if c not in market+['timestamp','return_pct','label_end']]
        for year in [2023,2024,2025,2026]:
            boundary=pd.Timestamp(f'{year}-01-01',tz='Asia/Kolkata')
            train=data[data.label_end<boundary-pd.Timedelta(days=1)]
            test=data[data.timestamp.dt.year==year].copy()
            # Nonoverlap within evaluation avoids scoring the same forward window repeatedly.
            keep=[];last=None
            for r in test.itertuples():
                if last is None or r.timestamp>=last:keep.append(r.Index);last=r.label_end
            test=test.loc[keep]
            if len(train)<100 or len(test)<30:continue
            y=np.where(train.return_pct>.05,2,np.where(train.return_pct<-.05,0,1))
            actual=np.where(test.return_pct>.05,2,np.where(test.return_pct<-.05,0,1))
            for name,cols in [('baseline',market),('market',market),('kp',kp),('combined',market+kp)]:
                categorical=[c for c in cols if c in cats];numeric=[c for c in cols if c not in cats]
                transform=ColumnTransformer([('category',OneHotEncoder(handle_unknown='ignore'),categorical),('numeric',StandardScaler(),numeric)])
                model=make_pipeline(transform,DummyClassifier(strategy='prior') if name=='baseline' else LogisticRegression(C=.1,max_iter=1000))
                model.fit(train[cols],y)
                raw=model.predict_proba(test[cols]);probs=np.zeros((len(test),3))
                for j,c in enumerate(model[-1].classes_):probs[:,int(c)]=raw[:,j]
                guess=probs.argmax(axis=1)
                summary.append(dict(model=name,version=version,kp_version=MODEL,horizon=h,year=year,partition='final test' if year==2026 else 'walk-forward validation',training_rows=len(train),test_rows=len(test),training_end=str(train.timestamp.max()),accuracy=float(accuracy_score(actual,guess)),balanced_accuracy=float(balanced_accuracy_score(actual,guess)),log_loss=float(log_loss(actual,probs,labels=[0,1,2])),brier=float(np.mean(np.sum((probs-np.eye(3)[actual])**2,axis=1))),confusion=confusion_matrix(actual,guess,labels=[0,1,2]).tolist()))
                for i,r in enumerate(test.itertuples()):predictions.append(dict(timestamp=str(r.timestamp),horizon=h,model=name,version=version,kind='historical out-of-sample replay',negative=float(probs[i,0]),neutral=float(probs[i,1]),positive=float(probs[i,2]),actual=int(actual[i]),prediction=int(guess[i]),return_percent=r.return_pct))
        (OUT/'metrics.json').write_text(json.dumps(summary,indent=2))
        pd.DataFrame(predictions).to_parquet(OUT/'predictions.parquet',index=False)
    return summary
if __name__=='__main__':
    result=train();print(json.dumps(result,indent=2))
