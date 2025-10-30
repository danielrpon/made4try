# made4try/user_auth/storage.py
from pathlib import Path
import sqlite3
from contextlib import contextmanager

# DB en la carpeta del paquete made4try (hermano de app.py)
DB_PATH = Path(__file__).resolve().parents[1] / "made4try.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict-like rows
    try:
        yield conn
    finally:
        conn.close()

def execute(sql: str, params: tuple = ()):
    """INSERT/UPDATE/DELETE. Devuelve lastrowid cuando aplique."""
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid

def query_one(sql: str, params: tuple = ()):
    """Devuelve un solo registro como dict o None."""
    with get_conn() as c:
        cur = c.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

def query_all(sql: str, params: tuple = ()):
    """Devuelve lista de dicts."""
    with get_conn() as c:
        cur = c.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]