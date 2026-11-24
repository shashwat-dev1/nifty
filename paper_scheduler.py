"""Restart-safe operator-controlled paper worker. Missed windows are never replayed."""
import json,threading,time
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from paper_service import ROOT,registry,eligibility,calendar,record_generated,settle
STOP=threading.Event()
DEFAULT={'enabled':False,'windows':['09:30','10:00','11:00','12:00','13:00','14:00'],'last_status':'disabled'}
def config():
    ROOT.mkdir(exist_ok=True);p=ROOT/'schedule.json'
    return json.loads(p.read_text()) if p.exists() else DEFAULT.copy()
def save(value):
    ROOT.mkdir(exist_ok=True);p=ROOT/'schedule.tmp';p.write_text(json.dumps(value,indent=2));p.replace(ROOT/'schedule.json')
def tick():
    c=config()
    if not c['enabled']:return
    now=datetime.now(timezone.utc);local=now.astimezone(ZoneInfo('Asia/Kolkata'))
    # Settlement recovery is independent of whether new forecasts are approved.
    from prediction_log import connection
    with connection() as ledger:
        pending=ledger.execute("select payload from events f where kind='forecast' and not exists(select 1 from events o where o.id='settlement-'||f.id)").fetchall()
    if pending:
        from custom_api import token,db
        from upstox_history import sync_minutes
        for raw, in pending:
            p=json.loads(raw);day=datetime.fromisoformat(p['timestamp']).astimezone(ZoneInfo('Asia/Kolkata')).date()
            list(sync_minutes(token(),day,local.date(),None))
        with db() as con:settle(con)
    candidates=[m for m in registry() if not eligibility(m)]
    if not candidates:c['last_status']='blocked: no approved model artifact'
    elif calendar(local.date())['status']!='verified trading':c['last_status']='blocked: session unknown or closed'
    else:
        from custom_api import token,db
        from market_status import status
        from paper_artifacts import load,predict
        from upstox_history import sync_minutes
        # Outcome refresh is restricted to current date, checkpoints preserve earlier data.
        list(sync_minutes(token(),local.date(),local.date(),None))
        with db() as con:settle(con)
        if local.strftime('%H:%M') not in c['windows']:c['last_status']='waiting; past windows are not backfilled'
        else:
            observation=status(token())['rows'][0]
            for model in candidates:
                artifact=load(model['artifact'],model['sha256'])
                output=predict(artifact,{'reference_price':observation['price']})
                record_generated(model,observation,output,local.strftime('%H:%M'))
            c['last_status']='eligible window processed'
    c['last_check']=now.isoformat();save(c)
def loop():
    while not STOP.wait(20):
        try:tick()
        except Exception:
            c=config();c['last_status']='worker error: data, artifact or eligibility check failed';save(c)
def start():
    STOP.clear();threading.Thread(target=loop,daemon=True,name='paper-worker').start()
