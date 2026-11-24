"""Bounded provider polling. Empty current sessions never become live prices."""
import threading,time
from datetime import timedelta
import pandas as pd
from kp_engine import IST
from upstox_history import fetch,normalize,verify_instrument
_lock=threading.Lock()
_cache=None
_at=0
def status(secret):
    global _cache,_at
    with _lock:
        if _cache is not None and time.monotonic()-_at<60:return _cache
        now=pd.Timestamp.now(tz=IST)
        result={'broker':'not configured','checked_at':now.isoformat(),'rows':[{'instrument':n,'price':None,'timestamp':None,'status':'unavailable','source':'Not connected'} for n in ['NIFTY 50','BANKNIFTY','INDIA VIX']]}
        if secret:
            try:
                verify_instrument()
                body=fetch(secret,now.date(),now.date(),True)
                bars=normalize(body,now.date(),now.date(),now)
                current=not bars.empty
                if bars.empty:
                    start=now.date()-timedelta(days=10)
                    bars=normalize(fetch(secret,start,now.date()-timedelta(days=1)),start,now.date()-timedelta(days=1),now)
                result['broker']='authenticated'
                result['current_session_candles']=len(body['data']['candles'])
                if not bars.empty:
                    r=bars.sort_values('timestamp').iloc[-1]
                    age=(now-r.timestamp).total_seconds()
                    result['rows'][0]={'instrument':'NIFTY 50','price':float(r.close),'timestamp':r.timestamp.isoformat(),'status':'recent polled candle' if current and age<180 else 'stale / last available','source':'Upstox 1-minute close','age_seconds':int(age)}
            except Exception as exc:result['broker']=str(exc)[:180]
        _cache=result;_at=time.monotonic()
        return result
