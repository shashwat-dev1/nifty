"""Backend-owned paper registry, idempotent windows and append-only settlement."""
import hashlib,json,sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from prediction_log import connection,PATH
from historical import MODEL
from minute_archive import attach_prices
ROOT=Path(__file__).parent/'archive/paper'
CHECKS=('training_data_verified','artifact_reproducible','chronological_validation','leakage_checks_pass','calibration_reviewed','interval_coverage_reviewed','baseline_comparison_documented')
def registry():
    ROOT.mkdir(exist_ok=True)
    path=ROOT/'registry.json'
    return json.loads(path.read_text()) if path.exists() else []
def eligibility(model):
    reasons=[k for k in CHECKS if model.get(k) is not True]
    artifact=Path(model.get('artifact',''))
    if not artifact.is_file():reasons.append('frozen artifact missing')
    elif hashlib.sha256(artifact.read_bytes()).hexdigest()!=model.get('sha256'):reasons.append('artifact digest mismatch')
    if not model.get('training_cutoff'):reasons.append('training cutoff missing')
    return reasons
def calendar(day):
    # No inferred weekday is promoted to an exchange-confirmed session.
    path=ROOT/'verified-sessions.json'
    records=json.loads(path.read_text()) if path.exists() else {}
    return records.get(str(day),{'status':'unverified','source':None})
def status():
    with connection() as con:
        rows=[{'id':i,'kind':k,'created':c,**json.loads(p)} for i,k,c,p in con.execute('select * from events order by created desc')]
    return {'models':[{'version':m.get('version'),'blockers':eligibility(m)} for m in registry()],
      'predictions':rows,'scheduling':'disabled until verified session and approved artifact exist',
      'windows':['09:00 premarket','09:30','10:00','11:00','12:00','13:00','14:00'],
      'calendar_today':calendar(datetime.now().date()),'approval':'Paper research eligibility only; no profitability claim'}
def record_generated(model,observation,output,window,path=PATH,now=None):
    now=now or datetime.now(timezone.utc)
    blockers=eligibility(model)
    if blockers:raise ValueError('Model blocked: '+', '.join(blockers))
    t=pd.Timestamp(observation['timestamp']);local=t.tz_convert('Asia/Kolkata')
    session=calendar(local.date())
    if session['status']!='verified trading':raise ValueError('Session not verified')
    if session.get('open') and session.get('close'):
        opening=pd.Timestamp(str(local.date())+'T'+session['open'],tz='Asia/Kolkata')
        closing=pd.Timestamp(str(local.date())+'T'+session['close'],tz='Asia/Kolkata')
        if local<opening or local>=closing:raise ValueError('Outside verified market session')
        if isinstance(model['horizon'],int) and local+pd.Timedelta(minutes=model['horizon'])>closing:raise ValueError('Horizon crosses market close')
    if not 0<=(pd.Timestamp(now)-t).total_seconds()<=120:raise ValueError('Stale or future observation')
    if pd.Timestamp(model['training_cutoff'])>=t:raise ValueError('Training cutoff overlaps decision')
    probs=np.array(output['probabilities'],dtype=float)
    if len(probs)!=3 or not np.isfinite(probs).all() or (probs<0).any() or not np.isclose(probs.sum(),1):raise ValueError('Invalid probabilities')
    if not output['lower_points']<=output['median_points']<=output['upper_points']:raise ValueError('Invalid movement interval')
    key=hashlib.sha256(f"{model['version']}|{window}|{local.date()}|{model['horizon']}".encode()).hexdigest()
    payload={'timestamp':t.isoformat(),'input_timestamp':t.isoformat(),'reference':observation['price'],'source':observation['source'],'model_version':model['version'],'training_cutoff':model['training_cutoff'],'horizon':model['horizon'],'kp_version':MODEL,'kind':'prospective paper','validation_status':'technically eligible paper research',**output}
    with connection(path) as con:
        con.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',[key,'forecast',now.isoformat(),json.dumps(payload)])
    return key
def settle(con,path=PATH,now=None):
    now=pd.Timestamp(now or datetime.now(timezone.utc))
    with connection(path) as ledger:
        forecasts=ledger.execute("select id,payload from events where kind='forecast'").fetchall()
        for key,raw in forecasts:
            if ledger.execute("select 1 from events where id=?",['settlement-'+key]).fetchone():continue
            p=json.loads(raw);h=p.get('horizon')
            t=pd.Timestamp(p['timestamp'])
            if isinstance(h,int):
                end=t+pd.Timedelta(minutes=h)
                if end>now:continue
                bars=attach_prices(con,pd.DataFrame({'timestamp':[t]}),h)
                if bars.exit_price.isna().iat[0]:continue
                reference=p['reference'];exit_price=float(bars.exit_price.iat[0])
            elif h in ('remaining_session','premarket_full_day','next_session'):
                from session_settlement import session_prices
                observed=session_prices(con,p)
                if observed is None:continue
                reference,exit_price,end=observed
                if end>now:continue
            else:continue
            points=float(exit_price-reference);pct=100*points/reference
            actual=2 if pct>p.get('neutral_percent',.05) else 0 if pct < -p.get('neutral_percent',.05) else 1
            error=points-p['expected_points']
            result={'forecast_id':key,'outcome_timestamp':end.isoformat(),'actual_points':points,'actual_percent':pct,'actual_class':actual,'correct':actual==int(np.argmax(p['probabilities'])),'absolute_error':abs(error),'squared_error':error**2,'inside_interval':p['lower_points']<=points<=p['upper_points']}
            ledger.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',['settlement-'+key,'outcome',now.isoformat(),json.dumps(result)])
