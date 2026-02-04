# metrics.py — Cálculos EFR/IF/ICR/TSS/FSS + EF/DA por ventana (best/decoupling_valid) + estimador VT2 (lite)
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

from .utils import ensure_datetime_sorted
from .config import ROLLING_WINDOW_SECONDS


# ============================================================
# Helpers: promedios ponderados y selección de ventana por tiempo real
# ============================================================

def _weighted_mean(x: pd.Series, w: pd.Series) -> float:
    x = pd.to_numeric(x, errors="coerce")
    w = pd.to_numeric(w, errors="coerce").fillna(0.0)
    m = x.notna() & w.notna() & (w > 0)
    if m.sum() == 0:
        return float("nan")
    return float((x[m] * w[m]).sum() / w[m].sum())


def _cv_weighted(x: pd.Series, w: pd.Series) -> float:
    """Coeficiente de variación (sd/mean) aproximado, ponderado por tiempo."""
    x = pd.to_numeric(x, errors="coerce")
    w = pd.to_numeric(w, errors="coerce").fillna(0.0)
    m = x.notna() & (w > 0)
    if m.sum() < 3:
        return float("nan")
    mu = _weighted_mean(x[m], w[m])
    if not np.isfinite(mu) or mu == 0:
        return float("nan")
    var = _weighted_mean((x[m] - mu) ** 2, w[m])
    if not np.isfinite(var):
        return float("nan")
    sd = float(np.sqrt(var))
    return float(sd / mu) if np.isfinite(sd) else float("nan")


def _hr_coverage(hr_raw: pd.Series) -> float:
    hr = pd.to_numeric(hr_raw, errors="coerce").astype(float)
    valid = hr.notna() & (hr > 0)
    return float(valid.mean()) if len(hr) else 0.0


def _compute_ef_da_for_segment(
    seg: pd.DataFrame,
    dt_s: pd.Series,
    intensity_for_ef: pd.Series,
    hr_raw: pd.Series,
    ef_kind: str,
) -> Tuple[float, float, float, float, float]:
    """
    Retorna: EF_win, DA_win_pct, EF_half1, EF_half2, hr_cov_segment

    ef_kind:
      - 'bike_power_hr'  -> EF = avg(power)/avg(HR)
      - 'run_speed_hr'   -> EF = avg(speed)/avg(HR)
    """
    # HR coverage del segmento (solo HR real)
    hr_cov = _hr_coverage(hr_raw.loc[seg.index])

    # pesos por tiempo
    w = pd.to_numeric(dt_s.loc[seg.index], errors="coerce").fillna(0.0).clip(lower=0.0)

    # EF ventana completa
    if ef_kind == "bike_power_hr":
        p_avg = _weighted_mean(intensity_for_ef.loc[seg.index], w)
        h_avg = _weighted_mean(hr_raw.loc[seg.index], w)
        ef_win = (p_avg / h_avg) if (np.isfinite(p_avg) and np.isfinite(h_avg) and h_avg > 0) else float("nan")
    elif ef_kind == "run_speed_hr":
        s_avg = _weighted_mean(intensity_for_ef.loc[seg.index], w)
        h_avg = _weighted_mean(hr_raw.loc[seg.index], w)
        ef_win = (s_avg / h_avg) if (np.isfinite(s_avg) and np.isfinite(h_avg) and h_avg > 0) else float("nan")
    else:
        ef_win = float("nan")

    # Partir en 2 mitades por tiempo (no por filas)
    el = pd.to_numeric(seg["elapsed_s"], errors="coerce").astype(float)
    mid = (float(el.min()) + float(el.max())) / 2.0
    seg1 = seg.loc[el <= mid]
    seg2 = seg.loc[el > mid]

    def _ef_block(block: pd.DataFrame) -> float:
        if len(block) < 3:
            return float("nan")
        wb = pd.to_numeric(dt_s.loc[block.index], errors="coerce").fillna(0.0).clip(lower=0.0)
        if ef_kind == "bike_power_hr":
            p = _weighted_mean(intensity_for_ef.loc[block.index], wb)
            h = _weighted_mean(hr_raw.loc[block.index], wb)
            return (p / h) if (np.isfinite(p) and np.isfinite(h) and h > 0) else float("nan")
        else:  # run_speed_hr
            s = _weighted_mean(intensity_for_ef.loc[block.index], wb)
            h = _weighted_mean(hr_raw.loc[block.index], wb)
            return (s / h) if (np.isfinite(s) and np.isfinite(h) and h > 0) else float("nan")

    ef1 = _ef_block(seg1)
    ef2 = _ef_block(seg2)
    da = ((ef2 / ef1) - 1.0) * 100.0 if (np.isfinite(ef1) and np.isfinite(ef2) and ef1 != 0) else float("nan")

    return ef_win, da, ef1, ef2, hr_cov


def find_best_window_timebased(
    m: pd.DataFrame,
    dt_s: pd.Series,
    intensity_for_score: pd.Series,
    hr_raw: Optional[pd.Series],
    window_secs: float,
    mode: str,
    *,
    min_hr_cov_global: float = 0.80,
    min_hr_cov_window: float = 0.90,
    max_cv_intensity: float = 0.15,
) -> Dict[str, Any]:
    """
    Selecciona la mejor ventana por tiempo real usando escaneo two-pointer.

    - Score = promedio ponderado por dt de intensity_for_score.
    - mode:
        'best'            -> sin restricciones extra
        'decoupling_valid'-> requiere HR coverage + estabilidad (CV) en la ventana
    """
    el = pd.to_numeric(m["elapsed_s"], errors="coerce").astype(float)
    if len(el) < 5:
        return {"ok": False, "reason": "too_few_points"}

    mode = str(mode).strip().lower()
    if mode not in ("best", "decoupling_valid"):
        mode = "best"

    # Gating global: sin HR real suficiente no existe decoupling_valid
    if mode == "decoupling_valid":
        if hr_raw is None:
            return {"ok": False, "reason": "no_hr"}
        if _hr_coverage(hr_raw) < min_hr_cov_global:
            return {"ok": False, "reason": "no_hr_global"}

    best: Dict[str, Any] = {"ok": False, "score": -float("inf")}

    n = len(m)
    i = 0
    while i < n:
        t0 = float(el.iloc[i])
        t1_target = t0 + float(window_secs)

        # mover j hasta cubrir la ventana
        j = i
        while j < n and float(el.iloc[j]) < t1_target:
            j += 1
        if j >= n:
            break

        seg = m.iloc[i:j].copy()
        if len(seg) < 5:
            i += 1
            continue

        w = pd.to_numeric(dt_s.loc[seg.index], errors="coerce").fillna(0.0).clip(lower=0.0)

        score = _weighted_mean(intensity_for_score.loc[seg.index], w)
        cv_int = _cv_weighted(intensity_for_score.loc[seg.index], w)

        if not np.isfinite(score):
            i += 1
            continue

        # Restricciones solo para decoupling_valid
        hr_cov_w = None
        if mode == "decoupling_valid":
            hr_cov_w = _hr_coverage(hr_raw.loc[seg.index])
            if hr_cov_w < min_hr_cov_window:
                i += 1
                continue
            # esfuerzo estable: CV bajo (si no puede calcular CV, descarta)
            if not np.isfinite(cv_int) or cv_int > max_cv_intensity:
                i += 1
                continue

        if score > float(best["score"]):
            best = {
                "ok": True,
                "start_s": float(seg["elapsed_s"].min()),
                "end_s": float(seg["elapsed_s"].max()),
                "score": float(score),
                "cv_intensity": float(cv_int) if np.isfinite(cv_int) else float("nan"),
                "hr_cov_window": float(hr_cov_w) if hr_cov_w is not None else None,
            }

        i += 1

    if not best.get("ok", False):
        return {"ok": False, "reason": "no_window_found"}
    return best


# ============================================================
# Métricas principales
# ============================================================

def add_metrics_minimal(
    df: pd.DataFrame,
    base_name: str,
    ftp: float,
    fc20: float,
    *,
    # NUEVO: ventana automática EF/DA
    window_mins: float | int | None = None,     # ej. 20 o 50
    window_mode: str = "best",                  # "best" | "decoupling_valid"
    sport: str | None = None,                   # None(auto) | "bike" | "run"
) -> pd.DataFrame:
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

    ftp = float(ftp)
    fc20 = float(fc20)

    power = pd.to_numeric(m["power_w"], errors="coerce").fillna(0.0).astype(float)
    hr_raw = pd.to_numeric(m["hr_bpm"], errors="coerce").astype(float)  # HR real (para DA)
    speed = pd.to_numeric(m["speed_kmh"], errors="coerce").astype(float)

    # %FTP y %FC_rel (protección contra divisiones por cero)
    m["pct_ftp"] = (power / ftp) * 100.0 if ftp > 0 else pd.Series([np.nan] * len(m), index=m.index)
    denom_fc = (hr_raw / fc20) * 100.0 if fc20 > 0 else pd.Series([np.nan] * len(m), index=m.index)
    denom_fc = denom_fc.replace([0.0, -0.0], np.nan)

    m["pct_fc_rel"] = denom_fc
    m["EFR"] = (m["pct_ftp"] / m["pct_fc_rel"]).replace([np.inf, -np.inf], np.nan)
    m["IF"] = (power / ftp) if ftp > 0 else pd.Series([np.nan] * len(m), index=m.index)
    m["ICR"] = (m["IF"] / m["EFR"]).replace([np.inf, -np.inf], np.nan)

    # Δt (segundos y horas)
    el = pd.to_numeric(m["elapsed_s"], errors="coerce").astype(float)
    dt = el.diff()
    first_dt = float(dt.dropna().iloc[0]) if dt.notna().any() else 1.0
    if not (first_dt > 0):
        first_dt = 1.0
    dt = dt.fillna(first_dt).clip(lower=0.0)
    dt_h = dt / 3600.0
    m["dt_s"] = dt

    # Cargas
    m["TSS_inc"] = (m["IF"] ** 2) * dt_h * 100.0
    m["FSS_inc"] = (m["ICR"].fillna(0.0) ** 2) * dt_h * 100.0
    m["TSS"] = m["TSS_inc"].cumsum()
    m["FSS"] = m["FSS_inc"].cumsum()

    # Ventana móvil aproximada según muestreo
    med_dt = max(first_dt, 1.0)
    n = max(1, int(round(ROLLING_WINDOW_SECONDS / med_dt)))
    m["TSS_inc_ma30"] = m["TSS_inc"].rolling(n, min_periods=1).mean()
    m["FSS_inc_ma30"] = m["FSS_inc"].rolling(n, min_periods=1).mean()
    m["power_ma30"] = power.rolling(n, min_periods=1).mean()
    m["hr_ma30"] = hr_raw.rolling(n, min_periods=1).mean()

    # Totales (solo primera fila)
    m["TSS_total"] = pd.NA
    m["FSS_total"] = pd.NA
    if len(m):
        m.loc[0, "TSS_total"] = m["TSS"].iloc[-1]
        m.loc[0, "FSS_total"] = m["FSS"].iloc[-1]

    # ============================================================
    # NUEVO: EF/DA por ventana (best / decoupling_valid)
    # ============================================================

    # Campos de salida
    m["WIN_mode"] = pd.NA
    m["WIN_mins"] = pd.NA
    m["WIN_signal"] = pd.NA
    m["WIN_start_s"] = pd.NA
    m["WIN_end_s"] = pd.NA
    m["WIN_score"] = pd.NA
    m["WIN_cv_intensity"] = pd.NA
    m["WIN_hr_cov"] = pd.NA
    m["WIN_reason"] = pd.NA

    m["EF_win"] = pd.NA
    m["DA_win_pct"] = pd.NA
    m["EF_half1"] = pd.NA
    m["EF_half2"] = pd.NA

    if window_mins is not None and len(m):
        try:
            win_secs = float(window_mins) * 60.0
            mode = str(window_mode).strip().lower()
            if mode not in ("best", "decoupling_valid"):
                mode = "best"

            # autodetección de deporte si no viene
            if sport is None:
                has_power = float(np.nansum(np.abs(power.to_numpy()))) > 0
                has_speed = float(np.nansum(np.abs(speed.fillna(0.0).to_numpy()))) > 0
                sport_use = "bike" if has_power else ("run" if has_speed else "bike")
            else:
                sport_use = str(sport).strip().lower()
                if sport_use not in ("bike", "run"):
                    sport_use = "bike"

            # define series de score + series para EF
            if sport_use == "bike":
                # score por avg IF (promedio ponderado por dt de power/ftp)
                intensity_score = (power / ftp) if ftp > 0 else pd.Series([np.nan] * len(m), index=m.index)
                intensity_ef = power  # EF = power/HR
                ef_kind = "bike_power_hr"
                win_signal = "if"
            else:
                intensity_score = speed.fillna(0.0)     # score por avg speed_kmh
                intensity_ef = speed.fillna(0.0)        # EF = speed/HR
                ef_kind = "run_speed_hr"
                win_signal = "speed_kmh"

            best = find_best_window_timebased(
                m=m,
                dt_s=m["dt_s"],
                intensity_for_score=intensity_score,
                hr_raw=hr_raw if mode == "decoupling_valid" else hr_raw,
                window_secs=win_secs,
                mode=mode,
                min_hr_cov_global=0.80,
                min_hr_cov_window=0.90,
                max_cv_intensity=0.15,
            )

            # escribe metadata básica
            m.loc[0, "WIN_mode"] = mode
            m.loc[0, "WIN_mins"] = float(window_mins)
            m.loc[0, "WIN_signal"] = win_signal

            if not best.get("ok", False):
                m.loc[0, "WIN_reason"] = best.get("reason", "no_window_found")
            else:
                s0 = float(best["start_s"])
                s1 = float(best["end_s"])
                seg = m.loc[(m["elapsed_s"].astype(float) >= s0) & (m["elapsed_s"].astype(float) <= s1)].copy()

                ef, da, ef1, ef2, hr_cov_seg = _compute_ef_da_for_segment(
                    seg=seg,
                    dt_s=m["dt_s"],
                    intensity_for_ef=intensity_ef,
                    hr_raw=hr_raw,
                    ef_kind=ef_kind,
                )

                # En decoupling_valid, refuerza la regla: HR suficiente en la ventana
                if mode == "decoupling_valid" and (not np.isfinite(hr_cov_seg) or hr_cov_seg < 0.90):
                    m.loc[0, "WIN_reason"] = "hr_insufficient_in_window"
                else:
                    m.loc[0, "WIN_start_s"] = s0
                    m.loc[0, "WIN_end_s"] = s1
                    m.loc[0, "WIN_score"] = float(best.get("score"))
                    m.loc[0, "WIN_cv_intensity"] = float(best.get("cv_intensity")) if best.get("cv_intensity") is not None else pd.NA
                    m.loc[0, "WIN_hr_cov"] = float(hr_cov_seg)

                    m.loc[0, "EF_win"] = float(ef) if np.isfinite(ef) else pd.NA
                    m.loc[0, "DA_win_pct"] = float(da) if np.isfinite(da) else pd.NA
                    m.loc[0, "EF_half1"] = float(ef1) if np.isfinite(ef1) else pd.NA
                    m.loc[0, "EF_half2"] = float(ef2) if np.isfinite(ef2) else pd.NA

        except Exception:
            # no rompas pipeline por ventana
            m.loc[0, "WIN_reason"] = "window_calc_error"

    return m


# ============================================================
# ---------- VT2 Estimator (lite) ----------
# ============================================================

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
    d["P_f"] = _ewma(pd.to_numeric(d["power_w"], errors="coerce"), tau_p_s, dt_rep)
    d["HR_f"] = _ewma(pd.to_numeric(d["hr_bpm"], errors="coerce"), tau_hr_s, dt_rep)
    d["EFF_f"] = _ewma(pd.to_numeric(d["EFF"], errors="coerce"), max(tau_p_s, tau_hr_s), dt_rep)

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

        dP_dt = _rolling_slope(t, p) * 60.0          # W/min
        dHR_dt = _rolling_slope(t, h) * 60.0         # bpm/min
        dEFFdP = _rolling_slope(p, e)                # (adim)/W
        a = _quad_curvature(p, e)

        cond_ramp = (dP_dt >= ramp_min_w_per_min)
        cond_flatHR = (abs(dHR_dt) <= dhr_flat_bpm_per_min)
        cond_plateau = (abs(dEFFdP) <= dEFFdP_eps_per_w)
        cond_curve = (a <= curvature_thresh)

        score = 0.0
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
        "vt2_hr_bpm": round(best["HR_mean"], 0),
        "vt2_eff": round(best["EFF_mean"], 3),
        "vt2_time_s": round(best["center_s"], 1),
        "window_s": int(W),
        "confidence_0_1": round(min(1.0, best["score"] / 4.0), 3),
        "eff_type": "EF_corr" if ("EF_corr" in d.columns and d["EF_corr"].notna().any()) else "EF_clasico",
        "diagnostics": best,
    }
    return est, pd.DataFrame(cands)
