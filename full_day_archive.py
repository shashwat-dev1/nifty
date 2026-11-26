"""Resumable calendar-day KP archive; exact full-day signatures, no market data."""
import csv,hashlib,json,sqlite3,os
from collections import Counter
from functools import lru_cache
from datetime import date,datetime,timedelta
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from kp_engine import KPChart,slots,IST
from historical import MODEL
ROOT=Path(__file__).parent/'archive/full-day-kp'
VERSION=hashlib.sha256(MODEL.encode()).hexdigest()[:16]
FIELDS=['date','time_ist','day_lord','moon_sign_lord','moon_star_lord','moon_sub_lord','lagna_lord','B12','B13','B14','B15','B16','B17','B18','kp_score','model']
def folder():
    p=ROOT/VERSION;p.mkdir(parents=True,exist_ok=True);return p
def calculate(day):
    rows=[]
    for t in slots(day):
        c=KPChart(t).calculate()
        rows.append([day.isoformat(),t.strftime('%H:%M'),*c['ruling_planets'].values(),*c['components'].values(),c['kp_score'],MODEL])
    # Signature excludes date/model, includes ordered time, all lords/components/score.
    canonical=json.dumps([r[1:-1] for r in rows],separators=(',',':'))
    return day.isoformat(),rows,hashlib.sha256(canonical.encode()).hexdigest(),canonical
def connection():
    con=sqlite3.connect(folder()/'index.sqlite3',timeout=30)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS days(day TEXT PRIMARY KEY,signature TEXT,canonical TEXT,rows_json TEXT)')
    con.execute('CREATE INDEX IF NOT EXISTS signature_index ON days(signature)')
    return con
def update(end=None,start=date(1995,1,1),workers=4):
    end=end or datetime.now(IST).date();p=folder()
    # Windows releases this process lock on crash; no stale-lock-file dead end.
    import msvcrt
    with open(p/'worker.lock','a+b') as lock:
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        with connection() as con:
            have={r[0] for r in con.execute('select day from days')}
            days=[];day=start
            while day<=end:
                if day.isoformat() not in have:days.append(day)
                day+=timedelta(days=1)
            total=(end-start).days+1
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for i,(day,rows,sig,canonical) in enumerate(pool.map(calculate,days,chunksize=8)):
                    con.execute('INSERT OR IGNORE INTO days VALUES(?,?,?,?)',[day,sig,canonical,json.dumps(rows)])
                    if i%32==0:con.commit()
                    (p/'progress.json').write_text(json.dumps({'status':'building','completed':len(have)+i+1,'total':total,'model':MODEL,'through':str(end)}))
            con.commit()
            temp=p/'full_day_kp.tmp'
            with temp.open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f);writer.writerow(FIELDS)
                for raw, in con.execute('select rows_json from days order by day'):writer.writerows(json.loads(raw))
            temp.replace(p/'full_day_kp_1995_present.csv')
            count=con.execute('select count(*) from days').fetchone()[0]
            (p/'progress.json').write_text(json.dumps({'status':'complete','completed':count,'total':total,'rows':count*26,'model':MODEL,'through':str(end),'csv':str(p/'full_day_kp_1995_present.csv')}))
def majority(rows):
    result={}
    for index,name in [(2,'day_lord'),(3,'moon_sign_lord'),(4,'moon_star_lord'),(5,'moon_sub_lord'),(6,'lagna_lord'),(14,'kp_score')]:
        counts=Counter(r[index] for r in rows);maximum=max(counts.values())
        result[name]={'values':sorted([k for k,v in counts.items() if v==maximum],key=str),'slots':maximum,'total':len(rows)}
    scores=[r[14] for r in rows]
    result['score_direction_counts']={'positive':sum(v>0 for v in scores),'negative':sum(v<0 for v in scores),'zero':sum(v==0 for v in scores)}
    return result

def score_majority(value):
    counts=value['score_direction_counts'];maximum=max(counts.values())
    return sorted(k for k,v in counts.items() if v==maximum)

def majority_key(value):
    return json.dumps({k:v['values'] for k,v in value.items() if k!='score_direction_counts'},sort_keys=True)

LORDS=['day_lord','moon_sign_lord','moon_star_lord','moon_sub_lord','lagna_lord']

def soft_comparison(selected,candidate):
    # Equal-weight modal lord overlap; tied modes receive proportional credit.
    agreements={k:len(set(selected[k]['values']) & set(candidate[k]['values']))/len(set(selected[k]['values']) | set(candidate[k]['values'])) for k in LORDS}
    matched=[k for k in LORDS if selected[k]['values']==candidate[k]['values']]
    if len(matched)<3:return None
    distribution=1-sum(abs(selected['score_direction_counts'][k]/selected['day_lord']['total']-candidate['score_direction_counts'][k]/candidate['day_lord']['total']) for k in ('positive','negative','zero'))/2
    return {'similarity_percent':round(100*(.85*sum(agreements.values())/5+.15*distribution),2),'lords_agree':len(matched),'matched_factors':', '.join(matched),'different_factors':', '.join(k for k in LORDS if k not in matched) or 'None','score_distribution_similarity_percent':round(100*distribution,2)}

@lru_cache(maxsize=2)
def majority_index(archive_path,count):
    with connection() as con:return [(day,majority(json.loads(raw))) for day,raw in con.execute('select day,rows_json from days order by day desc')]

def search(day):
    selected,rows,sig,canonical=calculate(day)
    with connection() as con:
        count=con.execute('select count(*) from days').fetchone()[0]
        matches=[r[0] for r in con.execute('select day from days where day<? and signature=? and canonical=? order by day desc',[selected,sig,canonical])]
    path=folder()/'progress.json'
    try:progress=json.loads(path.read_text())
    except (OSError,ValueError):progress={'status':'not started'}
    summary=majority(rows);key=majority_key(summary)
    index=majority_index(str(folder().resolve()),count)
    majority_matches=[d for d,m in index if d<selected and majority_key(m)==key]
    soft=[]
    for d,m in index:
        if d>=selected:continue
        comparison=soft_comparison(summary,m)
        if comparison:soft.append({'matching_date':d,**comparison})
    soft.sort(key=lambda r:(r['similarity_percent'],r['matching_date']),reverse=True)
    return {'selected_day':selected,'soft_matches':soft[:50],'soft_match_count':len(soft),'soft_definition':'At least 3 of 5 modal ruling lords must agree exactly. Rank = 85% equal-weight modal-lord overlap + 15% similarity of positive/negative/zero KP-score slot proportions. Ties use set overlap. This is descriptive similarity, not a probability or an identical timeline.','matches':matches,'majority':summary,'majority_matches':majority_matches,'score_majority':score_majority(summary),'direction_majority_matches':[d for d,m in index if d<selected and score_majority(m)==score_majority(summary)],'majority_definition':'Same modal values for each of the five ruling lords and KP score; ties preserved. Frequency counts need not be identical. This is not an exact timeline match.','indexed_days':count,'progress':progress,'definition':'All 26 slots 09:15–15:30 IST: exact five lords, B12–B18 components and KP score. Every calendar day included. Not identical planetary longitudes.','csv':str(folder()/'full_day_kp_1995_present.csv')}
def slot_search(timestamp):
    t=timestamp.astimezone(IST)
    c=KPChart(t).calculate()
    values=list(c['ruling_planets'].values())+[c['kp_score']]
    with connection() as con:
        con.execute('CREATE TABLE IF NOT EXISTS slots(timestamp TEXT PRIMARY KEY,day_lord TEXT,moon_sign_lord TEXT,moon_star_lord TEXT,moon_sub_lord TEXT,lagna_lord TEXT,kp_score REAL)')
        con.execute('CREATE INDEX IF NOT EXISTS slot_match ON slots(day_lord,moon_sign_lord,moon_star_lord,moon_sub_lord,lagna_lord,kp_score)')
        missing=con.execute("SELECT day,rows_json FROM days WHERE day NOT IN (SELECT substr(timestamp,1,10) FROM slots)").fetchall()
        for day,raw in missing:
            con.executemany('INSERT OR IGNORE INTO slots VALUES(?,?,?,?,?,?,?)',[(day+'T'+r[1]+':00+05:30',*r[2:7],r[14]) for r in json.loads(raw)])
        result=con.execute('SELECT * FROM slots WHERE substr(timestamp,1,10)<? AND day_lord=? AND moon_sign_lord=? AND moon_star_lord=? AND moon_sub_lord=? AND lagna_lord=? AND kp_score=? ORDER BY timestamp DESC',[t.date().isoformat(),*values]).fetchall()
    names=['timestamp',*LORDS,'kp_score']
    return {'selected_timestamp':t.isoformat(),'configuration':dict(zip(names[1:],values)),'total':len(result),'rows':[dict(zip(names,r)) for r in result],'definition':'Exact five ruling lords and KP score at any archived 15-minute slot on an earlier calendar day. Time of day need not agree. Market slot is the following 15 minutes, using candle-close timestamps; a complete slot requires all 15 one-minute candles.'}

if __name__=='__main__':update()
