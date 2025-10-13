# utils.py
from datetime import datetime
from io import BytesIO, TextIOWrapper
import gzip
import pandas as pd

def parse_iso8601_z(ts: str):
    try:
        if ts and ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts) if ts else None
    except Exception:
        return None

def to_float(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def to_int(x):
    try: return int(float(x))
    except (TypeError, ValueError): return None

def open_maybe_gzip_bytes(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".gz"):
        gz = gzip.GzipFile(fileobj=BytesIO(uploaded_file.getvalue()), mode="rb")
        return TextIOWrapper(gz, encoding="utf-8")
    return TextIOWrapper(BytesIO(uploaded_file.getvalue()), encoding="utf-8")

def clean_base_name(name: str) -> str:
    base = name
    if base.lower().endswith(".gz"): base = base[:-3]
    if base.lower().endswith(".tcx"): base = base[:-4]
    return base

def ensure_datetime_sorted(df: pd.DataFrame, col="time_utc") -> pd.DataFrame:
    if col in df.columns:
        dt = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_convert(None)
        df[col] = dt
        df = df.sort_values(col).reset_index(drop=True)
    return df