"""Server-only Firestore snapshot chunks and feedback; no Storage/billing required."""
import os,json,base64,hashlib,math
import threading
from concurrent.futures import ThreadPoolExecutor
_local=threading.local()
CHUNK=128*1024
def connection():
    if hasattr(_local,"connection"):return _local.connection
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    info=json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON'])
    credentials=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/datastore'])
    _local.connection=AuthorizedSession(credentials,refresh_timeout=15,max_refresh_attempts=1),'https://firestore.googleapis.com/v1/projects/'+info['project_id']+'/databases/(default)/documents/'
    return _local.connection

def document(path,value=None):
    session,base=connection()
    if value is None:
        response=session.get(base+path,timeout=(10,30),max_allowed_time=45)
        if response.status_code==404:return None
    else:
        fields={}
        for k,v in value.items():
            fields[k]={'booleanValue':v} if isinstance(v,bool) else {'integerValue':str(v)} if isinstance(v,int) else {'stringValue':str(v)}
        response=session.patch(base+path,json={'fields':fields},timeout=(10,30),max_allowed_time=45)
    response.raise_for_status()
    return {k:next(iter(v.values())) if 'integerValue' not in v else int(v['integerValue']) for k,v in response.json().get('fields',{}).items()}

def save_feedback(value):
    from datetime import datetime,timezone
    import uuid
    document('research_feedback/'+str(uuid.uuid4()),{**value,'created':datetime.now(timezone.utc).isoformat()})
    return {'saved':True}
def existing_chunks(ref):
    session,base=connection();existing={};page=None
    while True:
        params={'pageSize':1000,'mask.fieldPaths':'sha256'}
        if page:params['pageToken']=page
        response=session.get(base+ref+'/chunks',params=params,timeout=(10,30),max_allowed_time=45);response.raise_for_status()
        payload=response.json()
        for row in payload.get('documents',[]):existing[row['name'].rsplit('/',1)[-1]]=row.get('fields',{}).get('sha256',{}).get('stringValue')
        page=payload.get('nextPageToken')
        if not page:break
    return existing

def upload_snapshot(path,identifier):
    from pathlib import Path
    path=Path(path)
    if path.stat().st_size>128*1024*1024:raise ValueError('Snapshot exceeds 128 MiB deployment budget; reduce data before upload')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    ref='research_snapshots/'+identifier
    if document(ref) is not None:raise ValueError('Use a new immutable snapshot ID')
    count=math.ceil(path.stat().st_size/CHUNK)
    def put(index):
        with path.open('rb') as f:
            f.seek(index*CHUNK);chunk=f.read(CHUNK)
        document(ref+'/chunks/'+str(index).zfill(6),{'data':base64.b64encode(chunk).decode(),'sha256':hashlib.sha256(chunk).hexdigest()})
    # Resume only unverified chunks; do not re-upload successful documents.
    existing=existing_chunks(ref)
    pending=[]
    with path.open('rb') as f:
        for index in range(count):
            if existing.get(str(index).zfill(6))!=hashlib.sha256(f.read(CHUNK)).hexdigest():pending.append(index)
    from concurrent.futures import as_completed
    pool=ThreadPoolExecutor(max_workers=6)
    futures=[pool.submit(put,i) for i in pending]
    try:
        for completed,future in enumerate(as_completed(futures),1):
            future.result()
            if completed%25==0:print('Snapshot chunks transferred:',count-len(pending)+completed,'/',count,flush=True)
    finally:pool.shutdown(wait=True,cancel_futures=True)
    document(ref,{'complete':True,'chunks':count,'bytes':path.stat().st_size,'sha256':digest})
    return {'sha256':digest,'chunks':count,'bytes':path.stat().st_size}
def download_snapshot(path,identifier):
    ref='research_snapshots/'+identifier;meta=document(ref)
    if not meta or meta.get('complete') is not True or not 0<meta.get('chunks',0)<=1024 or not 0<meta.get('bytes',0)<=128*1024*1024:raise ValueError('Snapshot manifest unavailable or exceeds budget')
    def get(index):
        value=document(ref+'/chunks/'+str(index).zfill(6))
        if not value:raise ValueError('Snapshot chunk missing')
        data=base64.b64decode(value['data'],validate=True)
        if len(data)>CHUNK or hashlib.sha256(data).hexdigest()!=value['sha256']:raise ValueError('Snapshot chunk corrupt')
        return data
    total=0
    with open(path,'wb') as f,ThreadPoolExecutor(max_workers=6) as pool:
        for data in pool.map(get,range(meta['chunks'])):f.write(data);total+=len(data)
    if total!=meta['bytes']:raise ValueError('Snapshot size mismatch')
