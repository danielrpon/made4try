# made4try/user_auth/auth.py
import hashlib
import os
import hmac
from .storage import execute, query_one

# Iteraciones PBKDF2 para el formato nuevo
_ITER = 260_000


# ========= Formato NUEVO (recomendado): pbkdf2_sha256$iter$salt$dk =========
def hash_password(password: str) -> str:
    """Devuelve pbkdf2_sha256$ITER$SALTHEX$DKHEX"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${salt.hex()}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    """
    Verifica password contra stored.
    Soporta:
      - Formato nuevo:  pbkdf2_sha256$iter$salt$dk
      - Formato legado: hex:salt  (se valida con PBKDF2(100k) y SHA256)
    """
    if ":" in stored and "$" not in stored:
        # ----- Formato LEGADO: "hex:salt" -----
        try:
            pw_hex, salt_hex = stored.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
            return hmac.compare_digest(dk.hex(), pw_hex)
        except Exception:
            return False

    # ----- Formato NUEVO: "pbkdf2_sha256$iter$salt$dk" -----
    try:
        algo, iters, salt_hex, dk_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


# ========= Helpers LEGADO (solo para compatibilidad y migración) =========
def _hash_password_legacy(password: str, salt: bytes = None) -> tuple[str, bytes]:
    """
    Formato viejo: (hex, salt) con PBKDF2 100k. NO usar para nuevos usuarios.
    Lo mantenemos para validar y migrar.
    """
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex(), salt


def _verify_legacy(stored: str, password: str) -> bool:
    try:
        pw_hex, salt_hex = stored.split(":", 1)
        calc_hex, _ = _hash_password_legacy(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(calc_hex, pw_hex)
    except Exception:
        return False


# ========= API de alto nivel =========
def create_user(name: str, email: str, password: str, role: str = "athlete"):
    """
    Crea SIEMPRE con el formato NUEVO PBKDF2.
    """
    pw = hash_password(password)
    execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (name, email.lower().strip(), pw, role),
    )


def get_user_by_email(email: str):
    return query_one("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))


def login(email: str, password: str):
    """
    - Acepta ambos formatos de hash.
    - Si el usuario está en formato LEGADO y la clave es correcta,
      migra automáticamente a formato NUEVO más robusto.
    """
    row = get_user_by_email(email)
    if not row:
        return None

    stored = row.get("password_hash")
    if not stored:
        return None

    # Nuevo OK -> loguea
    if "$" in stored and check_password(password, stored):
        return dict(row)

    # Antiguo OK -> migrar a nuevo y loguear
    if ":" in stored and _verify_legacy(stored, password):
        new_hash = hash_password(password)
        execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))
        row["password_hash"] = new_hash
        return dict(row)

    # Falló
    return None