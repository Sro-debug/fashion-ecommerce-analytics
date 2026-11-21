"""Run every SQL file in sql/ against the SQLite DB and save results to outputs/tables/*.csv."""
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "myntra_analytics.db"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs" / "tables"


def run_all(verbose=True):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript((SQL_DIR / "00_views.sql").read_text())
    results = {}
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        if path.name.startswith("00_"):
            continue
        df = pd.read_sql_query(path.read_text(), con)
        df.to_csv(OUT_DIR / f"{path.stem}.csv", index=False)
        results[path.stem] = df
        if verbose:
            print(f"\n=== {path.stem} ({len(df)} rows) ===")
            print(df.head(25).to_string(index=False))
    con.close()
    return results


if __name__ == "__main__":
    run_all()
