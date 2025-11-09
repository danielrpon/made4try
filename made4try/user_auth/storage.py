# made4try/user_auth/storage.py
from pathlib import Path
import os, sqlite3
from contextlib import contextmanager

# Detectar ambiente cloud (Streamlit Cloud define variables de entorno, pero usamos una genérica)
IS_CLOUD = os.environ.get("STREAMLIT_RUNTIME") or os.environ.get("STREAMLIT_SERVER_ENABLED")

if IS_CLOUD:
    DB_PATH = Path("/tmp/made4try.db")         # ephemeral en la nube
else:
    DB_PATH = Path(__file__).resolve().parents[1] / "made4try.db"  # local junto al paquete

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_conn():
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