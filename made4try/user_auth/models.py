# made4try/user_auth/models.py
from .storage import execute, query_one
from .auth import hash_password

def get_user_by_email(email: str):
    email = email.lower().strip()
    return query_one("SELECT * FROM users WHERE email = ?", (email,))

def reset_password(email: str, new_password: str) -> int:
    """Devuelve cantidad de filas afectadas (0 si usuario no existe)."""
    email = email.lower().strip()
    user = get_user_by_email(email)
    if not user:
        return 0
    pw_hash = hash_password(new_password)
    execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email))
    return 1

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