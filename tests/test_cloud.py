import hashlib,zipfile,subprocess,os
from pathlib import Path
from cloud_bootstrap import restore
import pytest

def pack(tmp_path,name,entries):
 p=tmp_path/name
 with zipfile.ZipFile(p,'w') as z:
  for k,v in entries.items():z.writestr(k,v)
 return p,hashlib.sha256(p.read_bytes()).hexdigest()

def test_snapshot_rejects_tampering_and_traversal(tmp_path):
 p,digest=pack(tmp_path,'bad.zip',{'../outside':'no'})
 with pytest.raises(ValueError,match='checksum'):restore(p,'0'*64,tmp_path/'out')
 with pytest.raises(ValueError,match='path'):restore(p,digest,tmp_path/'out')
 assert not (tmp_path/'outside').exists()

def test_snapshot_requires_both_real_databases(tmp_path):
 p,digest=pack(tmp_path,'good.zip',{'archive/research.duckdb':'fixture','archive/full-day-kp/version/index.sqlite3':'fixture'})
 restore(p,digest,tmp_path/'out')
 assert (tmp_path/'out/archive/research.duckdb').read_text()=='fixture'
 p,digest=pack(tmp_path,'missing.zip',{'archive/research.duckdb':'fixture'})
 with pytest.raises(ValueError,match='KP slot'):restore(p,digest,tmp_path/'other')

def test_cloud_auth_fails_closed_in_isolated_process():
 code="""
from fastapi.testclient import TestClient
from cloud_backend import app
c=TestClient(app)
assert c.get('/api/health').json()=={'status':'ok'}
assert c.get('/api/daily-research?day=2026-11-25').status_code==401
assert c.get('/api/admin/jobs',headers={'Authorization':'Bearer '+ 'x'*40}).status_code==403
assert c.get('/custom_api.py',headers={'Authorization':'Bearer '+ 'x'*40}).status_code==403
"""
 env={**os.environ,'BACKEND_API_KEY':'x'*40,'NIFTY_CLOUD':'1'}
 subprocess.run([os.sys.executable,'-c',code],env=env,check=True,capture_output=True)
