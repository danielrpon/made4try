x# made4try/user_auth/storage.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "made4try.db"

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def execute(sql: str, params: tuple = ()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    return cur

def query_one(sql: str, params: tuple = ()):
    cur = get_conn().execute(sql, params)
    return cur.fetchone()

def query_all(sql: str, params: tuple = ()):
    cur = get_conn().execute(sql, params)
    return cur.fetchall()