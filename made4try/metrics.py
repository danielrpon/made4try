import numpy as np

def _weighted_mean(x: pd.Series, w: pd.Series) -> float:
    x = pd.to_numeric(x, errors="coerce")
    w = pd.to_numeric(w, errors="coerce").fillna(0.0)
    mask = x.notna() & w.notna() & (w > 0)
    if mask.sum() == 0:
        return float("nan")
    return float((x[mask] * w[mask]).sum() / w[mask].sum())

def _cv_weighted(x: pd.Series, w: pd.Series) -> float:
    """Coeficiente de variación ponderado (aprox). Útil para estabilidad."""
    x = pd.to_numeric(x, errors="coerce")
    w = pd.to_numeric(w, errors="coerce").fillna(0.0)
    mask = x.notna() & (w > 0)
    if mask.sum() < 3:
        return float("nan")
    xm = _weighted_mean(x[mask], w[mask])
    if not np.isfinite(xm) or xm == 0:
        return float("nan")
    var = _weighted_mean((x[mask] - xm) ** 2, w[mask])
    sd = float(np.sqrt(var)) if np.isfinite(var) else float("nan")
    return float(sd / xm) if np.isfinite(sd) else float("nan")

def _hr_coverage(hr_raw: pd.Series) -> float:
    hr = pd.to_numeric(hr_raw, errors="coerce")
    valid = hr.notna() & (hr > 0)
    return float(valid.mean()) if len(hr) else 0.0

def _compute_ef_da_for_segment(
    seg: pd.DataFrame,
    dt_s: pd.Series,
    intensity_series: pd.Series,
    hr_raw: pd.Series,
    ef_kind: str,
) -> tuple[float, float, float, float, float]:
    """
    Retorna: EF_win, DA_win_pct, EF_half1, EF_half2, hr_cov
    ef_kind: 'bike_power_hr' o 'run_speed_hr'
    """
    # HR coverage en segmento (solo HR real)
    hr_cov = _hr_coverage(hr_raw.loc[seg.index])

    # Promedios ponderados por tiempo
    w = dt_s.loc[seg.index].astype(float).clip(lower=0.0)

    if ef_kind == "bike_power_hr":
        # EF = avg(power) / avg(HR)
        p_avg = _weighted_mean(intensity_series.loc[seg.index], w)
        h_avg = _weighted_mean(hr_raw.loc[seg.index], w)
        ef_win = (p_avg / h_avg) if (np.isfinite(p_avg) and np.isfinite(h_avg) and h_avg > 0) else float("nan")
    elif ef_kind == "run_speed_hr":
        # EF_run = avg(speed) / avg(HR)
        s_avg = _weighted_mean(intensity_series.loc[seg.index], w)
        h_avg = _weighted_mean(hr_raw.loc[seg.index], w)
        ef_win = (s_avg / h_avg) if (np.isfinite(s_avg) and np.isfinite(h_avg) and h_avg > 0) else float("nan")
    else:
        ef_win = float("nan")

    # DA: drift de EF entre mitades
    el = pd.to_numeric(seg["elapsed_s"], errors="coerce").astype(float)
    mid = (float(el.min()) + float(el.max())) / 2.0

    seg1 = seg.loc[el <= mid]
    seg2 = seg.loc[el > mid]

    def _ef_block(block: pd.DataFrame) -> float:
        if len(block) < 3:
            return float("nan")
        wb = dt_s.loc[block.index].astype(float).clip(lower=0.0)
        if ef_kind == "bike_power_hr":
            p = _weighted_mean(intensity_series.loc[block.index], wb)
            h = _weighted_mean(hr_raw.loc[block.index], wb)
            return (p / h) if (np.isfinite(p) and np.isfinite(h) and h > 0) else float("nan")
        else:  # run_speed_hr
            s = _weighted_mean(intensity_series.loc[block.index], wb)
            h = _weighted_mean(hr_raw.loc[block.index], wb)
            return (s / h) if (np.isfinite(s) and np.isfinite(h) and h > 0) else float("nan")

    ef1 = _ef_block(seg1)
    ef2 = _ef_block(seg2)
    da = ((ef2 / ef1) - 1.0) * 100.0 if (np.isfinite(ef1) and np.isfinite(ef2) and ef1 != 0) else float("nan")

    return ef_win, da, ef1, ef2, hr_cov

def find_best_window_timebased(
    m: pd.DataFrame,
    dt_s: pd.Series,
    intensity_series: pd.Series,
    hr_raw: pd.Series | None,
    window_secs: float,
    mode: str,
    criterion: str,
    *,
    min_hr_cov_global: float = 0.80,
    min_hr_cov_window: float = 0.90,
    max_cv_intensity: float = 0.15,
) -> dict:
    """
    Encuentra la mejor ventana [start,end] por tiempo real.
    mode: 'best' o 'decoupling_valid'
    criterion: 'max_avg_if' o 'max_avg_speed'
    Retorna dict con start_s, end_s, score, cv, hr_cov_window, ok
    """
    el = pd.to_numeric(m["elapsed_s"], errors="coerce").astype(float)
    if len(el) < 5:
        return {"ok": False}

    # gating global para decoupling
    if mode == "decoupling_valid":
        if hr_raw is None or _hr_coverage(hr_raw) < min_hr_cov_global:
            return {"ok": False, "reason": "no_hr_global"}

    best = {"ok": False, "score": -float("inf")}

    # Two-pointer scan
    i = 0
    n = len(m)
    while i < n:
        t0 = float(el.iloc[i])
        t1 = t0 + float(window_secs)

        # mover j hasta cubrir ventana
        j = i
        while j < n and float(el.iloc[j]) < t1:
            j += 1
        if j >= n:
            break

        seg = m.iloc[i:j].copy()
        if len(seg) < 5:
            i += 1
            continue

        w = dt_s.loc[seg.index].astype(float).clip(lower=0.0)
        avg_int = _weighted_mean(intensity_series.loc[seg.index], w)
        cv_int = _cv_weighted(intensity_series.loc[seg.index], w)

        # HR coverage por ventana si aplica
        hr_cov_w = None
        if mode == "decoupling_valid":
            hr_cov_w = _hr_coverage(hr_raw.loc[seg.index])
            if hr_cov_w < min_hr_cov_window:
                i += 1
                continue
            if np.isfinite(cv_int) and cv_int > max_cv_intensity:
                i += 1
                continue

        # score según criterio
        if criterion == "max_avg_if" or criterion == "max_avg_speed":
            score = avg_int
        else:
            score = avg_int

        if np.isfinite(score) and score > best["score"]:
            best = {
                "ok": True,
                "start_s": float(seg["elapsed_s"].min()),
                "end_s": float(seg["elapsed_s"].max()),
                "score": float(score),
                "cv_intensity": float(cv_int) if np.isfinite(cv_int) else float("nan"),
                "hr_cov_window": float(hr_cov_w) if hr_cov_w is not None else None,
            }

        i += 1

    return best
