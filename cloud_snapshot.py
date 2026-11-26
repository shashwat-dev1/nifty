"""Create a consistent private data snapshot; stop local app before running."""
import argparse,hashlib,json,sqlite3,tempfile,zipfile
from pathlib import Path
import duckdb
ROOT=Path(__file__).resolve().parent

def build(output):
    from full_day_archive import folder
    # DuckDB exclusive writer lock fails if another process owns the database.
    with duckdb.connect(str(ROOT/'archive/research.duckdb')) as con:
        con.execute('CHECKPOINT')
        with tempfile.TemporaryDirectory() as temporary:
            copy=Path(temporary)/'index.sqlite3'
            with sqlite3.connect(folder()/'index.sqlite3') as source,sqlite3.connect(copy) as target:source.backup(target)
            with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
                z.write(ROOT/'archive/research.duckdb','archive/research.duckdb')
                z.write(copy,str((folder()/'index.sqlite3').relative_to(ROOT)).replace('\\','/'))
                for p in [folder()/'progress.json',ROOT/'archive/paper/verified-sessions.json']:
                    if p.is_file():z.write(p,p.relative_to(ROOT).as_posix())
    with open(output,'rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    Path(str(output)+'.sha256').write_text(digest)
    return digest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'archive/cloud-snapshot.zip'));parser.add_argument('--upload',action='store_true');args=parser.parse_args()
    checksum=build(args.output);print('Snapshot SHA256:',checksum)
    if args.upload:
        import os
        from cloud_firebase import upload_snapshot
        print(upload_snapshot(args.output,os.environ['FIREBASE_SNAPSHOT_ID']))
        print('Uploaded private snapshot. Set FIREBASE_SNAPSHOT_SHA256 in Render to the printed checksum.')
