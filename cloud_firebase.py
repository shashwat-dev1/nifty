"""Server-only Firestore snapshot chunks and feedback; no Storage/billing required."""
import os,json,base64,hashlib,math
from functools import lru_cache
CHUNK=384*1024
@lru_cache(maxsize=1)
def connection():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    info=json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON'])
    credentials=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/datastore'])
    return AuthorizedSession(credentials),'https://firestore.googleapis.com/v1/projects/'+info['project_id']+'/databases/(default)/documents/'

def document(path,value=None):
    session,base=connection()
    if value is None:
        response=session.get(base+path,timeout=30)
        if response.status_code==404:return None
    else:
        fields={}
        for k,v in value.items():
            fields[k]={'booleanValue':v} if isinstance(v,bool) else {'integerValue':str(v)} if isinstance(v,int) else {'stringValue':str(v)}
        response=session.patch(base+path,json={'fields':fields},timeout=30)
    response.raise_for_status()
    return {k:next(iter(v.values())) if 'integerValue' not in v else int(v['integerValue']) for k,v in response.json().get('fields',{}).items()}

def save_feedback(value):
    from datetime import datetime,timezone
    import uuid
    document('research_feedback/'+str(uuid.uuid4()),{**value,'created':datetime.now(timezone.utc).isoformat()})
    return {'saved':True}
def upload_snapshot(path,identifier):
    from pathlib import Path
    path=Path(path)
    if path.stat().st_size>128*1024*1024:raise ValueError('Snapshot exceeds 128 MiB deployment budget; reduce data before upload')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    ref='research_snapshots/'+identifier
    if document(ref) is not None:raise ValueError('Use a new immutable snapshot ID')
    count=0
    with path.open('rb') as f:
        while chunk:=f.read(CHUNK):
            document(ref+'/chunks/'+str(count).zfill(6),{'data':base64.b64encode(chunk).decode(),'sha256':hashlib.sha256(chunk).hexdigest()});count+=1
    document(ref,{'complete':True,'chunks':count,'bytes':path.stat().st_size,'sha256':digest})
    return {'sha256':digest,'chunks':count,'bytes':path.stat().st_size}
def download_snapshot(path,identifier):
    ref='research_snapshots/'+identifier;meta=document(ref)
    if not meta or meta.get('complete') is not True or not 0<meta.get('chunks',0)<=342 or not 0<meta.get('bytes',0)<=128*1024*1024:raise ValueError('Snapshot manifest unavailable or exceeds budget')
    total=0
    with open(path,'wb') as f:
        for i in range(meta['chunks']):
            value=document(ref+'/chunks/'+str(i).zfill(6))
            if not value:raise ValueError('Snapshot chunk missing')
            data=base64.b64decode(value['data'],validate=True)
            if len(data)>CHUNK or hashlib.sha256(data).hexdigest()!=value['sha256']:raise ValueError('Snapshot chunk corrupt')
            f.write(data);total+=len(data)
    if total!=meta['bytes']:raise ValueError('Snapshot size mismatch')
