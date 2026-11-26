"""Server-only Firestore snapshot chunks and feedback; no Storage/billing required."""
import os,json,base64,hashlib,math
from functools import lru_cache
CHUNK=384*1024
@lru_cache(maxsize=1)
def database():
    import firebase_admin
    from firebase_admin import credentials,firestore
    app=firebase_admin.initialize_app(credentials.Certificate(json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON'])))
    return firestore.client(app=app)
def save_feedback(value):
    from firebase_admin import firestore
    database().collection('research_feedback').add({**value,'created':firestore.SERVER_TIMESTAMP})
    return {'saved':True}
def upload_snapshot(path,identifier):
    from pathlib import Path
    path=Path(path)
    if path.stat().st_size>128*1024*1024:raise ValueError('Snapshot exceeds 128 MiB deployment budget; reduce data before upload')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    ref=database().collection('research_snapshots').document(identifier)
    if ref.get().exists:raise ValueError('Use a new immutable snapshot ID')
    count=0
    with path.open('rb') as f:
        while chunk:=f.read(CHUNK):
            ref.collection('chunks').document(str(count).zfill(6)).set({'data':base64.b64encode(chunk).decode(),'sha256':hashlib.sha256(chunk).hexdigest()});count+=1
    ref.set({'complete':True,'chunks':count,'bytes':path.stat().st_size,'sha256':digest})
    return {'sha256':digest,'chunks':count,'bytes':path.stat().st_size}
def download_snapshot(path,identifier):
    ref=database().collection('research_snapshots').document(identifier);meta=ref.get().to_dict()
    if not meta or meta.get('complete') is not True or not 0<meta.get('chunks',0)<=342 or not 0<meta.get('bytes',0)<=128*1024*1024:raise ValueError('Snapshot manifest unavailable or exceeds budget')
    total=0
    with open(path,'wb') as f:
        for i in range(meta['chunks']):
            value=ref.collection('chunks').document(str(i).zfill(6)).get().to_dict()
            if not value:raise ValueError('Snapshot chunk missing')
            data=base64.b64decode(value['data'],validate=True)
            if len(data)>CHUNK or hashlib.sha256(data).hexdigest()!=value['sha256']:raise ValueError('Snapshot chunk corrupt')
            f.write(data);total+=len(data)
    if total!=meta['bytes']:raise ValueError('Snapshot size mismatch')
