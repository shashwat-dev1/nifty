"""Verified-schedule settlement. Unknown schedules or any missing bar stay unresolved."""
import pandas as pd
from paper_service import calendar
def session_prices(con,p):
    t=pd.Timestamp(p['timestamp']).tz_convert('Asia/Kolkata');day=t.date()
    if p['horizon']=='next_session':
        # Never jump over an unknown day or infer closure from missing prices.
        for offset in range(1,15):
            candidate=(t+pd.Timedelta(days=offset)).date();c=calendar(candidate)
            if c['status']=='unverified':return None
            if c['status']=='verified trading':day=candidate;break
        else:return None
    c=calendar(day)
    if c['status']!='verified trading' or not c.get('open') or not c.get('close'):return None
    opening=pd.Timestamp(str(day)+'T'+c['open'],tz='Asia/Kolkata')
    end=pd.Timestamp(str(day)+'T'+c['close'],tz='Asia/Kolkata')
    start=t if p['horizon']=='remaining_session' else opening
    rows=con.execute('select timestamp,open,close from intraday where interval_minutes=1 and timestamp>? and timestamp<=? order by timestamp',[start,end]).df()
    expected=int((end-start).total_seconds()/60)
    if len(rows)!=expected or expected<=0:return None
    if not rows.timestamp.diff().dropna().eq(pd.Timedelta(minutes=1)).all():return None
    reference=p['reference'] if p['horizon']=='remaining_session' else rows.open.iloc[0]
    return float(reference),float(rows.close.iloc[-1]),end
