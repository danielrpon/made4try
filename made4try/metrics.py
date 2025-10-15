# =========================
# made4try/metrics.py
# =========================
import pandas as pd
from .config import (
    ROLLING_WINDOW_SECONDS,   # ventana para curvas de carga "MA30" (plot comparativo)
    HR_FILL_MA_SECONDS,       # ventana para rellenar FC inválida en el cálculo de FSS
    DISPLAY_SMOOTH_SECONDS,   # ventana por defecto para suavizar potencia/FC (solo visual)
)

def _secs_to_window(n_secs: float, first_dt: float) -> int:
    """Convierte segundos de ventana a nº de muestras según el dt observado."""
    try:
        w = int(round(float(n_secs) / float(first_dt)))
        return max(1, w)
    except Exception:
        return 1

def add_metrics_minimal(
    df: pd.DataFrame,
    base_name: str,
    ftp: float,
    fc20: float,
    smooth_secs: int | float | None = None,
) -> pd.DataFrame:
    """
    Calcula EFR/IF/ICR y las cargas TSS/FSS.
    - Rellena FC inválida (NaN/<=0) con un MA de HR_FILL_MA_SECONDS para que FSS no se rompa.
    - Genera columnas suavizadas (visual) power_smooth/hr_smooth con 'smooth_secs'
      (si es None, usa DISPLAY_SMOOTH_SECONDS de config.py).
    - Mantiene TSS/FSS independientes del suavizado visual.
    """
    df = df.copy()

    # -------- fecha y metadatos --------
    fecha = None
    if "time_utc" in df.columns and pd.api.types.is_datetime64_any_dtype(df["time_utc"]):
        if df["time_utc"].notna().any():
            fecha = df["time_utc"].dropna().iloc[0].date()

    # -------- dataframe mínimo 'm' --------
    m = pd.DataFrame({
        "fecha":     fecha.isoformat() if fecha else None,
        "documento": base_name,
        "elapsed_s": pd.to_numeric(df.get("elapsed_s"), errors="coerce"),
        "power_w":   pd.to_numeric(df.get("power_w"),   errors="coerce"),
        "hr_bpm":    pd.to_numeric(df.get("hr_bpm"),    errors="coerce"),
        "speed_kmh": pd.to_numeric(df.get("speed_kmh"), errors="coerce"),
    })

    # -------- parámetros --------
    ftp  = float(ftp)
    fc20 = float(fc20)

    power = m["power_w"].astype(float).fillna(0.0)
    hr    = m["hr_bpm"].astype(float)

    # -------- dt (segundos y horas) --------
    el = m["elapsed_s"].astype(float)
    dt = el.diff()
    first_dt = float(dt.dropna().iloc[0]) if dt.notna().any() else 1.0
    if not (first_dt > 0):
        first_dt = 1.0
    dt = dt.fillna(first_dt).clip(lower=0.0)
    dt_h = dt / 3600.0
    m["dt_s"] = dt

    # -------- FC efectiva para FSS (relleno con MA de HR_FILL_MA_SECONDS) --------
    n_fill = _secs_to_window(HR_FILL_MA_SECONDS, first_dt)
    hr_interp = hr.interpolate(limit_direction="both")
    hr_fill_ma = hr_interp.rolling(n_fill, min_periods=1).mean()

    invalid_hr = hr.isna() | (hr <= 0)
    hr_eff = hr.where(~invalid_hr, hr_fill_ma)
    if hr_eff.notna().sum() == 0:
        # si todo es inválido, evita NaNs en FSS
        hr_eff = hr_eff.fillna(0.0)

    # -------- métricas base (no dependen del suavizado visual) --------
    # %FTP & %FC_rel
    m["pct_ftp"]    = (power / ftp) * 100.0
    # Evita división 0/NaN si fc20 inválido
    m["pct_fc_rel"] = (hr_eff / fc20) * 100.0 if fc20 > 0 else pd.Series([pd.NA] * len(m), index=m.index, dtype="float")

    # EFR, IF, ICR
    efr = m["pct_ftp"] / m["pct_fc_rel"]
    IF  = power / ftp
    icr = IF / efr
    # Limpia infinitos que podrían aparecer si pct_fc_rel ~ 0
    icr = icr.replace([float("inf"), -float("inf")], float("nan"))

    # -------- cargas (incrementos y acumulados) --------
    tss_inc = (IF ** 2) * dt_h * 100.0
    fss_inc = ((icr.fillna(0.0)) ** 2) * dt_h * 100.0

    m["EFR"]     = efr
    m["IF"]      = IF
    m["ICR"]     = icr
    m["TSS_inc"] = tss_inc
    m["FSS_inc"] = fss_inc
    m["TSS"]     = tss_inc.cumsum()
    m["FSS"]     = fss_inc.cumsum()

    # -------- promedios móviles de carga para visualización (MA de ROLLING_WINDOW_SECONDS) --------
    n_plot = _secs_to_window(ROLLING_WINDOW_SECONDS, first_dt)
    m["TSS_inc_ma30"] = tss_inc.rolling(n_plot, min_periods=1).mean()
    m["FSS_inc_ma30"] = fss_inc.rolling(n_plot, min_periods=1).mean()

    # -------- suavizado visual de potencia/FC (NO afecta TSS/FSS) --------
    if smooth_secs is None:
        smooth_secs = DISPLAY_SMOOTH_SECONDS
    n_vis = _secs_to_window(smooth_secs, first_dt)

    # potencia: si hay huecos, interpola primero y luego MA(n_vis)
    p_interp = power.interpolate(limit_direction="both")
    m["power_smooth"] = p_interp.rolling(n_vis, min_periods=1).mean()

    # FC: usa hr (toma valores originales; para visual conviene interpolar también)
    h_interp = hr.interpolate(limit_direction="both")
    m["hr_smooth"] = h_interp.rolling(n_vis, min_periods=1).mean()

    # -------- totales en la primera fila --------
    m["TSS_total"] = pd.NA
    m["FSS_total"] = pd.NA
    if len(m):
        m.loc[m.index[0], "TSS_total"] = m["TSS"].iloc[-1]
        m.loc[m.index[0], "FSS_total"] = m["FSS"].iloc[-1]

    # Ordena por tiempo por si acaso
    if "elapsed_s" in m.columns:
        m = m.sort_values("elapsed_s").reset_index(drop=True)

    return m
