"""Build an allowlisted, price-free snapshot and store feedback independently."""
from contextlib import closing
import csv
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import duckdb

FEATURES = ("KP calculator", "Historical matches", "Backtesting results", "General experience")

def prepare_snapshot(project, output):
    parquet = project / "archive" / "snapshots.parquet"
    with duckdb.connect(":memory:") as src, closing(sqlite3.connect(output)) as dst:
        src.execute("SET TimeZone='Asia/Kolkata'")
        from historical import MODEL
        records = src.execute("""SELECT strftime(ts,'%Y-%m-%d %H:%M'),json_extract_string(details,'$.signature'),
            CAST(json_extract(details,'$.kp_score') AS DOUBLE) FROM read_parquet(?)
            WHERE model=? AND lat=26.9124 AND lon=75.7873 ORDER BY ts""", [str(parquet),MODEL]).fetchall()
        if not records:
            raise ValueError("No reference configurations for the installed engine")
        dst.execute("CREATE TABLE charts(stamp TEXT PRIMARY KEY,signature TEXT NOT NULL,score REAL NOT NULL)")
        dst.executemany("INSERT INTO charts VALUES (?,?,?)", records)
        dst.execute("CREATE INDEX matches ON charts(signature,stamp)")
        dst.execute("CREATE TABLE studies(study TEXT,period TEXT,n INTEGER,correct INTEGER,baseline INTEGER,PRIMARY KEY(study,period))")
        for study, file, date_col, outcome in (
            ("Daily walk-forward","daily_walk_forward.csv","day_key","actual"),
            ("Intraday holdout","intraday_holdout.csv","date","outcome"),
        ):
            counts = {}
            with (project/"archive"/"reports"/file).open(encoding="utf-8-sig",newline="") as f:
                for row in csv.DictReader(f):
                    period = row[date_col][:4]
                    totals = counts.setdefault(period,[0,0,0])
                    totals[0] += 1
                    totals[1] += float(row["prediction"]) == float(row[outcome])
                    totals[2] += float(row["baseline"]) == float(row[outcome])
            dst.executemany("INSERT INTO studies VALUES (?,?,?,?,?)",[(study,p,*v) for p,v in counts.items() if v[0]>=10])
        dst.commit()

def open_snapshot(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro&immutable=1",uri=True)

def add_feedback(path, feature, expected, actual, comments):
    fields = (expected,actual,comments)
    if feature not in FEATURES or not all(isinstance(v,str) and len(v)<=1800 for v in fields) or not (expected.strip() and actual.strip()):
        raise ValueError("Enter an expected and actual result, with at most 1,800 characters per field.")
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS feedback(created TEXT,feature TEXT,expected TEXT,actual TEXT,comments TEXT)")
        db.execute("INSERT INTO feedback VALUES (?,?,?,?,?)",(datetime.now(timezone.utc).isoformat(),feature,*fields))

