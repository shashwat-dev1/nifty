"""Restore private immutable research snapshot before starting Render."""
import hashlib,os,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def restore(archive,expected,destination):
    with open(archive,'rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if len(expected)!=64 or digest!=expected.lower():raise ValueError('Snapshot checksum mismatch')
    destination=Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist())>2_000_000_000:raise ValueError('Snapshot exceeds size limit')
        for i in z.infolist():
            target=(destination/i.filename).resolve()
            if not target.is_relative_to(destination) or not i.filename.startswith('archive/') or '\\' in i.filename:raise ValueError('Invalid snapshot path')
            if (i.external_attr>>16)&0o170000==0o120000:raise ValueError('Links forbidden')
        z.extractall(destination)
    if not (destination/'archive/research.duckdb').is_file():raise ValueError('Research database missing')
    if not list((destination/'archive/full-day-kp').glob('*/index.sqlite3')):raise ValueError('KP slot archive missing')

if __name__=='__main__':
    from cloud_firebase import download_snapshot
    temporary=ROOT/'snapshot-download.zip'
    download_snapshot(temporary,os.environ['FIREBASE_SNAPSHOT_ID'])
    restore(temporary,os.environ['FIREBASE_SNAPSHOT_SHA256'],ROOT)
    temporary.unlink()
    import duckdb
    from search_index import build
    with duckdb.connect(str(ROOT/'archive/research.duckdb')) as con:
        con.execute("SET memory_limit='128MB'");con.execute('SET threads=1');build(con)
    print('Verified snapshot scalar search lookup built.')
    print('Private snapshot checksum verified and restored. Cloud research worker disabled.')
