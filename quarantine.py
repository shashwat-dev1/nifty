"""Isolated unapproved evidence collection; never sets approval flags."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import numpy as np
from paper_service import ROOT,calendar
from paper_artifacts import load,predict
from prediction_log import connection
PATH=ROOT/'quarantined-observations.sqlite3'
def collect(model,observation,window,now=None,path=PATH):
    now=pd.Timestamp(now or datetime.now(timezone.utc));t=pd.Timestamp(observation['timestamp'])
    local=t.tz_convert('Asia/Kolkata');session=calendar(local.date())
    if session['status']!='verified trading' or not session.get('open') or not session.get('close'):raise ValueError('BLOCKED: verified session hours required')
    opening=pd.Timestamp(str(local.date())+'T'+session['open'],tz='Asia/Kolkata');closing=pd.Timestamp(str(local.date())+'T'+session['close'],tz='Asia/Kolkata')
    if not opening<=local<closing:raise ValueError('BLOCKED: outside session')
    if not isinstance(model['horizon'],int) or local+pd.Timedelta(minutes=model['horizon'])>closing:raise ValueError('BLOCKED: unsupported horizon or crosses close')
    if not 0<=(now-t).total_seconds()<=120:raise ValueError('BLOCKED: stale or future observation')
    if pd.Timestamp(model['training_cutoff'])>=t:raise ValueError('BLOCKED: cutoff')
    if observation.get('source')!='Upstox 1-minute close':raise ValueError('BLOCKED: unsupported source')
    if model.get('runtime')=='skops':
        from bundle_runtime import models,infer,live_features
        if model not in models():raise ValueError('BLOCKED: unregistered bundle')
        if not str(model['target']).isdigit():raise ValueError('BLOCKED: session target live feature contract not verified')
        output=infer(model,live_features(model,observation))
    else:
        if model not in __import__('paper_service').registry():raise ValueError('BLOCKED: model is not registered')
        artifact=load(model['artifact'],model['sha256'])
        output=predict(artifact,{'reference_price':observation['price']})
    key=hashlib.sha256(f"QUARANTINE|{model.get('runtime_id',model['version'])}|{local.date()}|{window}|{model['horizon']}".encode()).hexdigest()
    payload={'state':'QUARANTINED_PROSPECTIVE','kind':'unapproved prospective research only','timestamp':t.isoformat(),'created_timestamp':now.isoformat(),'input_timestamp':t.isoformat(),'reference':observation['price'],'source':observation['source'],'model_version':model.get('runtime_id',model['version']),'training_cutoff':model['training_cutoff'],'horizon':model['horizon'],'validation_status':'QUARANTINED / UNAPPROVED',**output}
    ROOT.mkdir(exist_ok=True)
    with connection(path) as con:con.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',[key,'forecast',now.isoformat(),json.dumps(payload)])
    return key
def status():
    ROOT.mkdir(exist_ok=True)
    with connection(PATH) as con:rows=[{'id':i,'event':k,'created':c,**json.loads(p)} for i,k,c,p in con.execute('select * from events order by created desc')]
    return {'state':'QUARANTINED_PROSPECTIVE','approval':'UNAPPROVED; isolated evidence only, never a trading recommendation','records':rows,'supported':'JSON baseline and checksum-verified skops elapsed horizons; session target live features blocked','model_availability':[{'id':m['runtime_id'],'target':m['target'],'model':m['model'],'status':'elapsed runtime available' if m['target'].isdigit() else 'BLOCKED: session live features'} for m in __import__('bundle_runtime').models()]}
