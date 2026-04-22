"""
Tool: run_migration.py
Purpose: Run a SQL migration file against the configured database.

Useful when you don't have psql installed locally. Uses the same
DATABASE_URL connection your app uses via tools/db.py.

Usage (from repo root, so `tools/` is on sys.path):
    python -m tools.run_migration migrations/003_api_call_log.sql
    conda run python -m tools.run_migration migrations/003_api_call_log.sql
"""
import argparse
import sys
from pathlib import Path

from tools.db import get_conn, _return_conn


def main():
    parser = argparse.ArgumentParser(description="Run a .sql migration file")
    parser.add_argument("path", help="Path to the .sql file to execute")
    args = parser.parse_args()

    sql_path = Path(args.path)
    if not sql_path.exists():
        print(f"ERROR: {sql_path} not found", file=sys.stderr)
        sys.exit(1)

    sql = sql_path.read_text()
    print(f"Running {sql_path}…")

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        print(f"OK — {sql_path.name} applied.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        _return_conn(conn)


if __name__ == "__main__":
    main()
