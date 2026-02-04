def _window_summary(df_final) -> str:
    """Resumen robusto para mostrar en UI (no en plot)."""
    if df_final is None or df_final.empty:
        return ""

    def _get(col):
        return df_final[col].iloc[0] if col in df_final.columns else None

    mode = _get("WIN_mode")
    mins = _get("WIN_mins")
    sig  = _get("WIN_signal")
    efr  = _get("EF_win")
    da   = _get("DA_win_pct")
    ws   = _get("WIN_start_s")
    we   = _get("WIN_end_s")
    reason = _get("WIN_reason")

    if reason is not None and pd.notna(reason) and str(reason).strip():
        return f"⚠️ Ventana: no disponible ({reason})"

    parts = []
    if mode is not None and pd.notna(mode): parts.append(f"modo: **{mode}**")
    if mins is not None and pd.notna(mins): parts.append(f"ventana: **{float(mins):.0f} min**")
    if sig  is not None and pd.notna(sig):  parts.append(f"señal: **{sig}**")
    if efr  is not None and pd.notna(efr):  parts.append(f"EFR(rel): **{float(efr):.3f}**")
    if da   is not None and pd.notna(da):   parts.append(f"DA: **{float(da):.2f}%**")
    if ws is not None and we is not None and pd.notna(ws) and pd.notna(we):
        parts.append(f"rango: **{_fmt_mmss(ws)} → {_fmt_mmss(we)}**")

    return " | ".join(parts)
