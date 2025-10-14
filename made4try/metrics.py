# made4try/metrics.py
import pandas as pd
from .config import ROLLING_WINDOW_SECONDS  # ya lo usas para ventanas

def add_metrics_minimal(df: pd.DataFrame, base_name: str, ftp: float, fc20: float) -> pd.DataFrame:
    df = df.copy()
    # ... (código inicial igual: fecha, construcción de m, etc.)
    
    power = m["power_w"]
    hr = m["hr_bpm"].astype(float)

    # --- Ventana móvil en segundos -> número de muestras según el dt observado ---
    el = m["elapsed_s"].astype(float)
    dt = el.diff()
    first_dt = float(dt.dropna().iloc[0]) if dt.notna().any() else 1.0
    if not (first_dt > 0):
        first_dt = 1.0
    dt = dt.fillna(first_dt).clip(lower=0.0)
    dt_h = dt / 3600.0
    m["dt_s"] = dt

    # >>> Nuevo: reemplazo de FC faltante con promedio móvil de 10 s
    REPLACE_HR_WITH_MA_SECS = 10  # <-- cambia a 5/15/etc si lo prefieres
    n10 = max(1, int(round(REPLACE_HR_WITH_MA_SECS / first_dt)))

    # Interpolamos primero (si hay pequeños huecos), luego MA(n10)
    hr_interp = hr.interpolate(limit_direction="both")
    hr_ma10   = hr_interp.rolling(n10, min_periods=1).mean()

    # Usamos la FC efectiva: si la FC original es NaN o <=0, usamos el MA10
    invalid_hr = hr.isna() | (hr <= 0)
    hr_eff = hr.where(~invalid_hr, hr_ma10)

    # Si TODA la serie de FC es NaN/0, hr_eff será NaN => tratamos FSS como 0
    if hr_eff.notna().sum() == 0:
        hr_eff = hr_eff.fillna(0.0)

    # %FTP y %FC_rel
    m["pct_ftp"] = (power / float(ftp)) * 100.0
    m["pct_fc_rel"] = (hr_eff / float(fc20)) * 100.0

    # EFR, IF, ICR
    efr = m["pct_ftp"] / m["pct_fc_rel"]
    IF  = power / float(ftp)
    icr = IF / efr

    # Si por algún motivo quedan NaN (p.ej., FC20=0), no rompas el acumulado
    icr = icr.replace([float("inf"), -float("inf")], float("nan"))

    # Incrementos de carga
    tss_inc = (IF ** 2) * dt_h * 100.0
    # clave: si ICR es NaN en alguna muestra, ese incremento se considera 0
    fss_inc = ((icr.fillna(0.0)) ** 2) * dt_h * 100.0

    # Acumulados
    m["TSS_inc"] = tss_inc
    m["FSS_inc"] = fss_inc
    m["TSS"] = tss_inc.cumsum()
    m["FSS"] = fss_inc.cumsum()

    # Promedios móviles para visualización (usa ventana global de 30 s ya existente)
    from .config import ROLLING_WINDOW_SECONDS
    n = max(1, int(round(ROLLING_WINDOW_SECONDS / first_dt)))
    m["TSS_inc_ma30"] = tss_inc.rolling(n, min_periods=1).mean()
    m["FSS_inc_ma30"] = fss_inc.rolling(n, min_periods=1).mean()
    m["power_ma30"]   = power.rolling(n, min_periods=1).mean()
    m["hr_ma30"]      = hr_eff.rolling(n, min_periods=1).mean()

    # Totales en la primera fila
    m["TSS_total"] = pd.NA
    m["FSS_total"] = pd.NA
    if len(m):
        m.loc[0, "TSS_total"] = m["TSS"].iloc[-1]
        m.loc[0, "FSS_total"] = m["FSS"].iloc[-1]

    return m
