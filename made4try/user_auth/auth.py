# made4try/user_auth/auth.py
import hashlib, os, hmac
from .storage import execute, query_one

# --- hashing con salt (simple y portátil)
def _hash_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
    if salt is None:
        salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return pw_hash.hex(), salt

def create_user(name: str, email: str, password: str, role: str = "athlete"):
    pw_hex, salt = _hash_password(password)
    execute("""
      INSERT INTO users (name, email, password_hash, role)
      VALUES (?, ?, ?, ?)
    """, (name, email.lower().strip(), f"{pw_hex}:{salt.hex()}", role))

def get_user_by_email(email: str):
    return query_one("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))

def verify_password(stored_hash_with_salt: str, password: str) -> bool:
    pw_hex, salt_hex = stored_hash_with_salt.split(":")
    calc_hex, _ = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(calc_hex, pw_hex)

def login(email: str, password: str):
    row = get_user_by_email(email)
    if not row:
        return None
    if verify_password(row["password_hash"], password):
        return dict(row)
    return None