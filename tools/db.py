"""
Database helper module for Solclear.
Provides connection pooling and simple query helpers for Postgres on Railway.

Usage:
    from tools.db import fetch_all, fetch_one, execute

    orgs = fetch_all("SELECT * FROM organizations")
    org = fetch_one("SELECT * FROM organizations WHERE id = %s", (1,))
    execute("INSERT INTO organizations (name) VALUES (%s)", ("Acme Solar",))
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_conn():
    """Get a database connection. Uses DATABASE_URL from env."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    return psycopg2.connect(DATABASE_URL)


def fetch_all(query, params=None):
    """Execute a query and return all rows as dicts."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_one(query, params=None):
    """Execute a query and return the first row as a dict, or None."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def execute(query, params=None):
    """Execute a write query (INSERT/UPDATE/DELETE). Returns the cursor for lastrowid etc."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur
    finally:
        conn.close()


def execute_returning(query, params=None):
    """Execute a write query with RETURNING clause. Returns the first row as a dict."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        conn.commit()
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
