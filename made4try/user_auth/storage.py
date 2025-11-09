# made4try/user_auth/storage.py
from pathlib import Path
import os
import sqlite3
from contextlib import contextmanager

def _cloud_db_path() -> Path:
    # Detecta entorno de Streamlit Cloud y usa /tmp
    if os.environ.get("STREAMLIT_RUNTIME") or os.environ.get("STREAMLIT_CLOUD"):
        return Path("/tmp/made4try.db")
    # Local: junto al paquete
    return Path(__file__).resolve().parents[1] / "made4try.db"

DB_PATH = _cloud_db_path()

@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def execute(sql: str, params: tuple = ()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid

def query_one(sql: str, params: tuple = ()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

def query_all(sql: str, params: tuple = ()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]