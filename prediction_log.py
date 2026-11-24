"""Append-only forecast/event ledger. Unvalidated models cannot create forecasts."""
import sqlite3,json,uuid
from datetime import datetime,timezone
from pathlib import Path
PATH=Path(__file__).parent/'archive/prediction-ledger.sqlite3'
def connection(path=PATH):
    con=sqlite3.connect(path)
    con.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,kind TEXT,created TEXT,payload TEXT)')
    for operation in ['UPDATE','DELETE']:
        con.execute(f"CREATE TRIGGER IF NOT EXISTS no_{operation.lower()} BEFORE {operation} ON events BEGIN SELECT RAISE(ABORT,'append only'); END")
    return con
def record_forecast(payload,path=PATH):
    now=datetime.now(timezone.utc)
    decision=datetime.fromisoformat(payload['timestamp'])
    available=datetime.fromisoformat(payload['input_timestamp'])
    if decision.tzinfo is None or available.tzinfo is None:raise ValueError('Timezone required')
    if decision<now or available>now:raise ValueError('Prospective decision must not predate creation; inputs must already be available')
    if payload.get('validation_status')!='approved prospective':raise ValueError('No model approved for prospective use')
    probs=payload['probabilities']
    if len(probs)!=3 or any(p<0 or p>1 for p in probs) or abs(sum(probs)-1)>1e-8:raise ValueError('Invalid probabilities')
    key=uuid.uuid4().hex
    with connection(path) as con:con.execute('INSERT INTO events VALUES(?,?,?,?)',[key,'forecast',now.isoformat(),json.dumps(payload)])
    return key
def append_outcome(forecast_id,payload,path=PATH):
    with connection(path) as con:
        original=con.execute("select payload from events where id=? and kind='forecast'",[forecast_id]).fetchone()
        if original is None:raise ValueError('Forecast not found')
        forecast=json.loads(original[0])
        end=datetime.fromisoformat(payload['outcome_timestamp'])
        if end>datetime.now(timezone.utc) or end<=datetime.fromisoformat(forecast['timestamp']):raise ValueError('Outcome is not mature')
        if con.execute("select 1 from events where kind='outcome' and json_extract(payload,'$.forecast_id')=?",[forecast_id]).fetchone():raise ValueError('Outcome already recorded')
        con.execute('INSERT INTO events VALUES(?,?,?,?)',[uuid.uuid4().hex,'outcome',datetime.now(timezone.utc).isoformat(),json.dumps({**payload,'forecast_id':forecast_id})])
