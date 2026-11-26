"""Render entrypoint: restricted research API, authenticated by Vercel server."""
import os,hmac
from starlette.responses import JSONResponse
from custom_api import app
SECRET=os.environ['BACKEND_API_KEY']
if len(SECRET)<32:raise ValueError('BACKEND_API_KEY must contain at least 32 characters')
GET={'/api/health','/api/coverage','/api/upstox','/api/market','/api/candles','/api/timeline','/api/daily-research','/api/kp/slot-matches','/api/trajectory-metrics','/api/historical-forecast'}
POST={'/api/calculate','/api/matches','/api/statistics','/api/feedback'}
@app.middleware('http')
async def cloud_guard(request,call_next):
    if request.url.path=='/api/health' and request.method=='GET':return JSONResponse({'status':'ok'})
    if not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+SECRET):return JSONResponse({'detail':'Unauthorized'},401)
    allowed=request.url.path in (GET if request.method=='GET' else POST if request.method=='POST' else set())
    if not allowed:return JSONResponse({'detail':'Unavailable in cloud research mode'},403)
    return await call_next(request)
