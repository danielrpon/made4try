# metrics.py
import pandas as pd
from .utils import ensure_datetime_sorted
from .config import ROLLING_WINDOW_SECONDS

def add_metrics_minimal(df: pd.DataFrame, base_name: str, ftp: float, fc20: float) -> pd.DataFrame:
    df = ensure_datetime_sorted(df.copy(), "time_utc")

    # Fecha del primer punto
    fecha = None
    if "time_utc" in df and df["time_utc"].notna().any():
        fecha = df["time_utc"].dropna().iloc[0].date().isoformat()

    m = pd.DataFrame({
        "fecha": fecha,
        "documento": base_name,
        "elapsed_s": pd.to_numeric(df.get("elapsed_s"), errors="coerce"),
        "power_w":   pd.to_numeric(df.get("power_w"),   errors="coerce").fillna(0.0),
        "hr_bpm":    pd.to_numeric(df.get("hr_bpm"),    errors="coerce"),
        "speed_kmh": pd.to_numeric(df.get("speed_kmh"), errors="coerce"),
    })

    ftp = float(ftp); fc20 = float(fc20)
    power = m["power_w"]
    hr = m["hr_bpm"].astype(float)

    m["pct_ftp"]   = (power/ftp)*100.0
    m["pct_fc_rel"]= (hr/fc20)*100.0
    m["EFR"]       = m["pct_ftp"] / m["pct_fc_rel"]
    m["IF"]        = power/ftp
    m["ICR"]       = m["IF"] / m["EFR"]

    # Δt
    el = m["elapsed_s"].astype(float)
    dt = el.diff()
    first_dt = float(dt.dropna().iloc[0]) if dt.notna().any() else 1.0
    if not (first_dt > 0): first_dt = 1.0
    dt = dt.fillna(first_dt).clip(lower=0.0)
    dt_h = dt/3600.0
    m["dt_s"] = dt

    # Cargas
    m["TSS_inc"] = (m["IF"]  **2) * dt_h * 100.0
    m["FSS_inc"] = (m["ICR"] **2) * dt_h * 100.0
    m["TSS"] = m["TSS_inc"].cumsum()
    m["FSS"] = m["FSS_inc"].cumsum()

    # Ventana móvil aproximada según muestreo
    # Si el muestreo no es 1s, se usa n = ceil(ROLLING_WINDOW_SECONDS / med_dt)
    med_dt = max(first_dt, 1.0)
    n = max(1, int(round(ROLLING_WINDOW_SECONDS / med_dt)))
    m["TSS_inc_ma30"] = m["TSS_inc"].rolling(n, min_periods=1).mean()
    m["FSS_inc_ma30"] = m["FSS_inc"].rolling(n, min_periods=1).mean()
    m["power_ma30"]   = power.rolling(n, min_periods=1).mean()
    m["hr_ma30"]      = m["hr_bpm"].rolling(n, min_periods=1).mean()

    # Totales (solo primera fila)
    m["TSS_total"] = pd.NA
    m["FSS_total"] = pd.NA
    if len(m):
        m.loc[0,"TSS_total"] = m["TSS"].iloc[-1]
        m.loc[0,"FSS_total"] = m["FSS"].iloc[-1]
    return m