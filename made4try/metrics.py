# made4try/metrics.py
import pandas as pd
from .config import (
    ROLLING_WINDOW_SECONDS,   # ventana para curvas de carga que ya mostrabas
    DISPLAY_SMOOTH_SECONDS,   # nuevo: suavizado de potencia/FC para visualización
    HR_FILL_MA_SECONDS,       # nuevo: reemplazo de FC inválida al calcular FSS
)

def add_metrics_minimal(df: pd.DataFrame, base_name: str, ftp: float, fc20: float) -> pd.DataFrame:
    """
    Calcula EFR/IF/ICR y las cargas TSS/FSS.
    - Rellena huecos/valores inválidos de FC con un promedio móvil de HR_FILL_MA_SECONDS
      para que FSS/ICR no se rompan.
    - Crea señales suavizadas de potencia y FC (DISPLAY_SMOOTH_SECONDS) SOLO para visualización.
    """
    df = df.copy()

    # ---------------- fecha y metadatos ----------------
    fecha = None
    if "time_utc" in df.columns and pd.api.types.is_datetime64_any_dtype(df["time_utc"]):
        if df["time_utc"].notna().any():
            fecha = df["time_utc"].dropna().iloc[0].date()

    df["fecha"] = fecha.isoformat() if fecha else None
    df["documento"] = base_name

    # ---------------- dataframe mínimo m ----------------
    m = pd.DataFrame({
        "fecha":      df.get("fecha"),
        "documento":  df.get("documento"),
        "elapsed_s":  pd.to_numeric(df.get("elapsed_s"), errors="coerce"),
        "power_w":    pd.to_numeric(df.get("power_w"),   errors="coerce"),
        "hr_bpm":     pd.to_numeric(df.get("hr_bpm"),    errors="coerce"),
        "speed_kmh":  pd.to_numeric(df.get("speed_kmh"), errors="coerce"),
    })

    # ---------------- parámetros ----------------
    ftp  = float(ftp)
    fc20 = float(fc20)

    power = m["power_w"].fillna(0.0)
    hr    = m["hr_bpm"].astype(float)

    # ---------------- dt (segundos y horas) ----------------
    el = m["elapsed_s"].astype(float)
    dt = el.diff()
    first_dt = float(dt.dropna().iloc[0]) if dt.notna().any() else 1.0
    if not (first_dt > 0):
        first_dt = 1.0
    dt = dt.fillna(first_dt).clip(lower=0.0)
    dt_h = dt / 3600.0
    m["dt_s"] = dt

    # ---------------- FC efectiva (relleno con MA de HR_FILL_MA_SECONDS) ----------------
    n_fill = max(1, int(round(HR_FILL_MA_SECONDS / first_dt)))

    hr_interp = hr.interpolate(limit_direction="both")
    hr_ma     = hr_interp.rolling(n_fill, min_periods=1).mean()

    invalid_hr = hr.isna() | (hr <= 0)
    hr_eff = hr.where(~invalid_hr, hr_ma)

    if hr_eff.notna().sum() == 0:
        hr_eff = hr_eff.fillna(0.0)

    # ---------------- NUEVO: señales suavizadas para visualización ----------------
    n_disp = max(1, int(round(DISPLAY_SMOOTH_SECONDS / first_dt)))
    m["power_smooth"] = power.interpolate(limit_direction="both").rolling(n_disp, min_periods=1).mean()
    m["hr_smooth"]    = hr.interpolate(limit_direction="both").rolling(n_disp, min_periods=1).mean()

    # ---------------- métricas base ----------------
    m["pct_ftp"]    = (power / ftp) * 100.0
    m["pct_fc_rel"] = (hr_eff / fc20) * 100.0

    efr = m["pct_ftp"] / m["pct_fc_rel"]
    IF  = power / ftp
    icr = IF / efr
    icr = icr.replace([float("inf"), -float("inf")], float("nan"))

    # ---------------- cargas (incrementos y acumulados) ----------------
    tss_inc = (IF ** 2) * dt_h * 100.0
    fss_inc = ((icr.fillna(0.0)) ** 2) * dt_h * 100.0

    m["TSS_inc"] = tss_inc
    m["FSS_inc"] = fss_inc
    m["TSS"]     = tss_inc.cumsum()
    m["FSS"]     = fss_inc.cumsum()

    # ---------------- promedios móviles para visualización de incrementos ----------------
    n_plot = max(1, int(round(ROLLING_WINDOW_SECONDS / first_dt)))
    m["TSS_inc_ma30"] = tss_inc.rolling(n_plot, min_periods=1).mean()
    m["FSS_inc_ma30"] = fss_inc.rolling(n_plot, min_periods=1).mean()
    m["power_ma30"]   = power.rolling(n_plot, min_periods=1).mean()
    m["hr_ma30"]      = hr_eff.rolling(n_plot, min_periods=1).mean()

    # ---------------- totales en la primera fila ----------------
    m["TSS_total"] = pd.NA
    m["FSS_total"] = pd.NA
    if len(m):
        m.loc[0, "TSS_total"] = m["TSS"].iloc[-1]
        m.loc[0, "FSS_total"] = m["FSS"].iloc[-1]

    return m
