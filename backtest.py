"""Chronological, leakage-aware historical event matching on NIFTY 50 close bars.
Inputs: timestamp,close; timestamps are ISO 8601 WITH timezone, bars mark close time.
"""
from __future__ import annotations
import csv, math
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import defaultdict
from kp_engine import KPChart, IST, normalize_time


def read_prices(path: str) -> list[tuple[datetime,float]]:
    out=[]
    with open(path,newline='',encoding='utf-8-sig') as f:
        rdr=csv.DictReader(f)
        if not rdr.fieldnames or not {'timestamp','close'}.issubset(rdr.fieldnames):
            raise ValueError('CSV needs timestamp,close columns')
        for r in rdr:
            dt=normalize_time(datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')))
            price=float(r['close'])
            if price<=0 or not math.isfinite(price):raise ValueError('Invalid close')
            out.append((dt,price))
    out.sort(key=lambda x:x[0]); times=[x[0] for x in out]
    if len(set(times))!=len(times):raise ValueError('Duplicate bar timestamps')
    return out


def make_events(prices, horizon_minutes=15, step_minutes=15, include_unchanged=False):
    if horizon_minutes<1 or step_minutes<1:raise ValueError('Positive intervals required')
    lookup=dict(prices)
    events=[]
    for ts, px in prices:
        if ts.weekday()>=5 or not (9<=ts.hour<=15):continue
        minute=ts.hour*60+ts.minute
        if not (9*60+15<=minute<=15*60+30-horizon_minutes):continue
        if (minute-(9*60+15))%step_minutes!=0:continue
        future=ts+timedelta(minutes=horizon_minutes)
        if future.date()!=ts.date() or future not in lookup:continue
        chart=KPChart(ts).calculate()
        ret=(lookup[future]/px)-1
        events.append({'timestamp':ts,'date':ts.date(),'signature':chart['signature'],
                       'kp_score':chart['kp_score'],'majority':chart['majority'],
                       'return':ret,'up':int(ret>0),'down':int(ret<0)})
    return events


def wilson_interval(successes,n,z=1.96):
    if n==0:return (None,None)
    p=successes/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (max(0,center-half),min(1,center+half))


def summarize(events):
    n=len(events); wins=sum(e['up'] for e in events)
    lo,hi=wilson_interval(wins,n)
    return {'n':n,'up':wins,'down':sum(e['down'] for e in events),
            'flat':n-wins-sum(e['down'] for e in events),
            'up_fraction':round(wins/n,4) if n else None,
            'up_95pct_wilson_low':round(lo,4) if lo is not None else None,
            'up_95pct_wilson_high':round(hi,4) if hi is not None else None,
            'mean_forward_return_pct':round(100*sum(e['return'] for e in events)/n,5) if n else None}


def history_report(events, split_date: date, minimum_history=10):
    """Only events with strictly earlier dates can inform a test event.
    Also outputs aggregated training vs test; overlapping historical events remain dependent.
    """
    train=[x for x in events if x['date']<split_date]
    test=[x for x in events if x['date']>=split_date]
    historical=defaultdict(list)
    for e in train:historical[e['signature']].append(e)
    matches=[]
    for e in test:
        refs=historical.get(e['signature'],[])
        # Only use train history, never use future test period for signal selection.
        if len(refs)>=minimum_history:
            matches.append({'timestamp':e['timestamp'].isoformat(),'signature':e['signature'],
                            'prior_count':len(refs),'prior_up_frequency':round(sum(x['up'] for x in refs)/len(refs),4),
                            'observed_forward_return_pct':round(100*e['return'],5),'observed_up':e['up']})
    return {'training':summarize(train),'test':summarize(test),
            'test_matched':len(matches),'matches':matches,
            'notes':'Research only. No commissions/slippage. Matching rows are not independent. Train/test split is fixed.'}


def save_events(events,path):
    with open(path,'w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f,fieldnames=['timestamp','date','signature','kp_score','majority','return','up','down']);wr.writeheader()
        for e in events:wr.writerow({**e,'timestamp':e['timestamp'].isoformat(),'date':e['date'].isoformat()})
