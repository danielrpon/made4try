# metrics.py — Cálculos EFR/IF/ICR/TSS/FSS y estimador VT2 (lite)
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

from .utils import ensure_datetime_sorted
from .config import ROLLING_WINDOW_SECONDS


def add_metrics_minimal(df: pd.DataFrame, base_name: str, ftp: float, fc20: float) -> pd.DataFrame:
    df = ensure_datetime_sorted(df.copy(), "time_utc")

    # Fecha del primer punto
    fecha = None
    if "time_utc" in df.columns and df["time_utc"].notna().any():
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

    m["pct_ftp"]    = (power / ftp) * 100.0
    m["pct_fc_rel"] = (hr / fc20) * 100.0
    m["EFR"]        = m["pct_ftp"] / m["pct_fc_rel"]
    m["IF"]         = power / ftp
    m["ICR"]        = m["IF"] / m["EFR"]

    # Δt
    el = m["elapsed_s"].astype(float)
    dt = el.diff()
    first_dt = float(dt.dropna().iloc[0]) if dt.notna().any() else 1.0
    if not (first_dt > 0):
        first_dt = 1.0
    dt = dt.fillna(first_dt).clip(lower=0.0)
    dt_h = dt / 3600.0
    m["dt_s"] = dt

    # Cargas
    m["TSS_inc"] = (m["IF"]  ** 2) * dt_h * 100.0
    m["FSS_inc"] = (m["ICR"] ** 2) * dt_h * 100.0
    m["TSS"] = m["TSS_inc"].cumsum()
    m["FSS"] = m["FSS_inc"].cumsum()

    # Ventana móvil aproximada según muestreo
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
        m.loc[0, "TSS_total"] = m["TSS"].iloc[-1]
        m.loc[0, "FSS_total"] = m["FSS"].iloc[-1]
    return m


# ---------- VT2 Estimator (lite) ----------
def _ewma(series: pd.Series, tau_s: float, dt_s: float = 1.0) -> pd.Series:
    """EWMA causal simple con constante de tiempo tau_s (s)."""
    if tau_s <= 0:
        return series.copy()
    alpha = dt_s / (tau_s + dt_s)
    out = []
    prev = None
    for x in pd.to_numeric(series, errors="coerce").astype(float).to_numpy():
        if prev is None or np.isnan(prev):
            prev = x
        else:
            prev = alpha * x + (1.0 - alpha) * prev
        out.append(prev)
    return pd.Series(out, index=series.index)


def _rolling_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Pendiente (dy/dx) por regresión lineal centrada."""
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 10:
        return float("nan")
    x0 = x[m] - x[m].mean()
    y0 = y[m] - y[m].mean()
    denom = (x0 * x0).sum()
    if denom == 0:
        return float("nan")
    return float((x0 * y0).sum() / denom)


def _quad_curvature(x: np.ndarray, y: np.ndarray) -> float:
    """Ajuste cuadrático y ~ a x^2 + b x + c; devuelve 'a' (curvatura)."""
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 15:
        return float("nan")
    a, b, c = np.polyfit(x[m], y[m], 2)
    return float(a)


def _compute_eff_for_vt2(df: pd.DataFrame, ftp: Optional[float], hr_ftp: Optional[float]) -> pd.DataFrame:
    """Crea la columna EFF usada por el estimador (prefiere EF_corr/EFR si existe)."""
    d = df.copy()
    if "EF_corr" in d.columns and d["EF_corr"].notna().any():
        d["EFF"] = pd.to_numeric(d["EF_corr"], errors="coerce")
    elif "EFR" in d.columns and d["EFR"].notna().any():
        d["EFF"] = pd.to_numeric(d["EFR"], errors="coerce")
        d["EF_corr"] = d["EFF"]
    elif ftp and hr_ftp and ftp > 0 and hr_ftp > 0:
        d["EFF"] = (pd.to_numeric(d["power_w"], errors="coerce") / ftp) / \
                   (pd.to_numeric(d["hr_bpm"], errors="coerce") / hr_ftp)
        d["EF_corr"] = d["EFF"]
    else:
        d["EFF"] = (pd.to_numeric(d["power_w"], errors="coerce") /
                    pd.to_numeric(d["hr_bpm"], errors="coerce")).replace([np.inf, -np.inf], np.nan)
    return d


def estimate_vt2(
    df_final: pd.DataFrame,
    *,
    ftp: Optional[float],
    hr_ftp: Optional[float],
    window_s: int = 180,
    ramp_min_w_per_min: float = 6.0,
    dhr_flat_bpm_per_min: float = 0.5,
    dEFFdP_eps_per_w: float = 0.002,
    tau_p_s: float = 7.0,
    tau_hr_s: float = 20.0,
    curvature_thresh: float = -1e-5,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Devuelve (estimacion, candidatos) usando df_final de la app.
    Requisitos mínimos: elapsed_s, power_w, hr_bpm, dt_s.
    """
    d = _compute_eff_for_vt2(df_final, ftp, hr_ftp).copy()

    # dt representativo
    dt_rep = float(np.nanmedian(d["dt_s"])) if "dt_s" in d.columns else 1.0
    d["P_f"]   = _ewma(pd.to_numeric(d["power_w"], errors="coerce"), tau_p_s, dt_rep)
    d["HR_f"]  = _ewma(pd.to_numeric(d["hr_bpm"], errors="coerce"), tau_hr_s, dt_rep)
    d["EFF_f"] = _ewma(pd.to_numeric(d["EFF"],    errors="coerce"), max(tau_p_s, tau_hr_s), dt_rep)

    n = len(d)
    W = max(60, min(window_s, n - 5))
    cands = []

    for start in range(0, n - W):
        end = start + W
        w = d.iloc[start:end]

        t = w["elapsed_s"].to_numpy()
        p = w["P_f"].to_numpy()
        h = w["HR_f"].to_numpy()
        e = w["EFF_f"].to_numpy()

        dP_dt  = _rolling_slope(t, p) * 60.0          # W/min
        dHR_dt = _rolling_slope(t, h) * 60.0          # bpm/min
        dEFFdP = _rolling_slope(p, e)                 # (adim)/W
        a      = _quad_curvature(p, e)

        cond_ramp    = (dP_dt >= ramp_min_w_per_min)
        cond_flatHR  = (abs(dHR_dt) <= dhr_flat_bpm_per_min)
        cond_plateau = (abs(dEFFdP) <= dEFFdP_eps_per_w)
        cond_curve   = (a <= curvature_thresh)

        score  = 0.0
        score += 1.0 if cond_ramp else 0.0
        score += 1.0 if cond_flatHR else 0.0
        score += 1.0 if cond_plateau else 0.0
        score += 0.5 if cond_curve else 0.0
        if cond_ramp:
            score += min(1.0, (dP_dt - ramp_min_w_per_min) / 6.0) * 0.3
        score += max(0.0, (1.0 - abs(dHR_dt) / max(1e-6, dhr_flat_bpm_per_min))) * 0.3
        score += max(0.0, (1.0 - abs(dEFFdP) / max(1e-6, dEFFdP_eps_per_w))) * 0.6

        cands.append({
            "start_s": float(w["elapsed_s"].iloc[0]),
            "end_s": float(w["elapsed_s"].iloc[-1]),
            "center_s": float(0.5 * (w["elapsed_s"].iloc[0] + w["elapsed_s"].iloc[-1])),
            "P_mean": float(np.nanmean(p)),
            "HR_mean": float(np.nanmean(h)),
            "EFF_mean": float(np.nanmean(e)),
            "dP_dt_w_per_min": float(dP_dt),
            "dHR_dt_bpm_per_min": float(dHR_dt),
            "dEFFdP_per_w": float(dEFFdP),
            "curvature_a": float(a),
            "score": float(score),
            "flags": {
                "ramp": bool(cond_ramp),
                "flat_hr": bool(cond_flatHR),
                "plateau": bool(cond_plateau),
                "curvature_concave": bool(cond_curve),
            },
        })

    if not cands:
        raise ValueError("Sin candidatos: ventana demasiado grande o datos insuficientes.")

    P_all = d["P_f"].to_numpy()
    p70 = float(np.nanpercentile(P_all, 70))
    p95 = float(np.nanpercentile(P_all, 95))

    ranked = sorted(cands, key=lambda x: x["score"], reverse=True)
    ranked_pref = [c for c in ranked if p70 <= c["P_mean"] <= p95] or ranked
    best = ranked_pref[0]

    est = {
        "vt2_power_w": round(best["P_mean"], 1),
        "vt2_hr_bpm":  round(best["HR_mean"], 0),
        "vt2_eff":     round(best["EFF_mean"], 3),
        "vt2_time_s":  round(best["center_s"], 1),
        "window_s":    int(W),
        "confidence_0_1": round(min(1.0, best["score"] / 4.0), 3),
        "eff_type":    "EF_corr" if ("EF_corr" in d.columns and d["EF_corr"].notna().any()) else "EF_clasico",
        "diagnostics": best,
    }
    return est, pd.DataFrame(cands)