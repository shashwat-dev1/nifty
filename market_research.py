"""Explicit longer-horizon observations. No inference across absent minute bars."""
import pandas as pd
from minute_archive import attach_prices

def outcomes(con,frame,mode='elapsed',minutes=15):
    if mode=='elapsed':return attach_prices(con,frame,minutes)
    if mode not in ('remainder','next_session','next_day_close'):raise ValueError('Unknown outcome definition')
    result=frame.copy()
    result['close']=float('nan');result['exit_price']=float('nan')
    sessions=con.sql("select timestamp::date day,min(timestamp) first,max(timestamp) last from intraday where interval_minutes=1 group by 1 order by 1").fetchall()
    for i,row in result.iterrows():
        t=pd.Timestamp(row.timestamp)
        reference=con.execute('select close from intraday where timestamp=? and interval_minutes=1',[t]).fetchall()
        if not reference:continue
        result.at[i,'close']=reference[0][0]
        current=next((s for s in sessions if s[0]==t.tz_convert('Asia/Kolkata').date()),None)
        following=next((s for s in sessions if s[0]>t.tz_convert('Asia/Kolkata').date()),None)
        if mode=='remainder' and current:
            span=int((current[2]-t).total_seconds()/60)
            if span>0:
                observed=attach_prices(con,pd.DataFrame({'timestamp':[t]}),span)
                result.at[i,'exit_price']=observed.exit_price.iat[0]
        elif following:
            # Only an immediately following known daily trading date qualifies.
            expected=con.execute("select min(day) from daily where instrument='NIFTY 50' and day>?",[t.date()]).fetchall()[0][0]
            if expected!=following[0]:continue
            bars=con.execute('select open,close from intraday where timestamp in (?,?) order by timestamp',[following[1],following[2]]).fetchall()
            if len(bars)!=2:continue
            if mode=='next_session':result.at[i,'close']=bars[0][0]
            elif current:
                result.at[i,'close']=con.execute('select close from intraday where timestamp=?',[current[2]]).fetchall()[0][0]
            result.at[i,'exit_price']=bars[-1][1]
    return result
