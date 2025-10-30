# made4try/user_auth/storage.py
from pathlib import Path
import sqlite3
from contextlib import contextmanager

# Base de datos en la carpeta del paquete made4try (junto a app.py)
DB_PATH = Path(__file__).resolve().parents[1] / "made4try.db"

@contextmanager
def get_conn():
    """Crea y gestiona conexión SQLite con row_factory tipo dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # acceso tipo dict
    try:
        yield conn
    finally:
        conn.close()

def execute(sql: str, params: tuple = ()):
    """INSERT, UPDATE o DELETE. Retorna lastrowid si aplica."""
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
    """Devuelve una lista de registros (dict)."""
    with get_conn() as c:
        cur = c.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []