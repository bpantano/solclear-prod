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
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Connection pool: min 2, max 10 connections
_pool = None


def _get_pool():
    """Get or create the connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set in environment")
        _pool = psycopg2.pool.SimpleConnectionPool(2, 10, DATABASE_URL)
    return _pool


def get_conn():
    """Get a connection from the pool."""
    return _get_pool().getconn()


def _return_conn(conn):
    """Return a connection to the pool."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


def fetch_all(query, params=None):
    """Execute a query and return all rows as dicts."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        _return_conn(conn)


def fetch_one(query, params=None):
    """Execute a query and return the first row as a dict, or None."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _return_conn(conn)


def execute(query, params=None):
    """Execute a write query (INSERT/UPDATE/DELETE). Returns the cursor for lastrowid etc."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur
    finally:
        _return_conn(conn)


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
        _return_conn(conn)
