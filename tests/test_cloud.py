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

def test_snapshot_builder_copies_database_consistently(tmp_path,monkeypatch):
    import cloud_snapshot as snapshot
    import full_day_archive as archive
    import duckdb,sqlite3,zipfile
    root=tmp_path/'project';folder=root/'archive/full-day-kp/version';folder.mkdir(parents=True)
    with duckdb.connect(str(root/'archive/research.duckdb')) as con:
        con.execute('create table example(value int)');con.execute('insert into example values (7)')
    con=sqlite3.connect(folder/'index.sqlite3');con.execute('create table days(day text)');con.execute("insert into days values ('2023-01-04')");con.commit();con.close()
    monkeypatch.setattr(snapshot,'ROOT',root);monkeypatch.setattr(archive,'folder',lambda:folder)
    output=tmp_path/'snapshot.zip';digest=snapshot.build(output)
    restore(output,digest,tmp_path/'restored')
    with duckdb.connect(str(tmp_path/'restored/archive/research.duckdb')) as con:assert con.execute('select value from example').fetchone()==(7,)

def test_firestore_chunk_round_trip_and_missing_chunk(tmp_path,monkeypatch):
    import cloud_firebase as f
    records={}
    def memory(path,value=None):
        if value is not None:records[path]=value
        return records.get(path)
    monkeypatch.setattr(f,'document',memory)
    source=tmp_path/'source.zip';source.write_bytes(b'isolated-fixture'*40000)
    result=f.upload_snapshot(source,'fixture-v1')
    assert result['chunks']==2
    output=tmp_path/'restored.zip';f.download_snapshot(output,'fixture-v1')
    assert output.read_bytes()==source.read_bytes()
    assert all(len(v.get('data',''))<1048576 for v in records.values())
    del records['research_snapshots/fixture-v1/chunks/000000']
    with pytest.raises(ValueError,match='missing'):f.download_snapshot(output,'fixture-v1')
