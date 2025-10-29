# made4try/user_auth/models.py
from .storage import execute

def init_db():
    # Usuarios
    execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'athlete',  -- 'athlete' | 'admin'
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );""")

    # Resumen de entrenos por archivo (vinculado al usuario)
    execute("""
    CREATE TABLE IF NOT EXISTS workouts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      file_name TEXT NOT NULL,
      date TEXT,
      tss_total REAL,
      fss_total REAL,
      duration_h REAL,
      avg_power REAL,
      avg_hr REAL,
      efr_avg REAL,
      icr_avg REAL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );""")

    # Bitácora subjetiva (opcional futuro)
    execute("""
    CREATE TABLE IF NOT EXISTS diaries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      date TEXT NOT NULL,
      sleep_quality INTEGER,       -- 1..5
      nutrition_quality INTEGER,   -- 1..5
      mood INTEGER,                -- 1..5
      stress INTEGER,              -- 1..5
      notes TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(user_id, date),
      FOREIGN KEY(user_id) REFERENCES users(id)
    );""")