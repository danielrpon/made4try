# made4try/app.py — Streamlit entrypoint (AUTH + TCX + Metrics + EF/DA + VT2)

# ---------- Path bootstrap ----------
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PARENT = BASE_DIR.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from made4try.config import PAGE_TITLE, PAGE_ICON, LAYOUT

# ---------- Libs ----------
import streamlit as st
from io import BytesIO
import zipfile
import pandas as pd

# ---------- App modules ----------
from made4try.utils import clean_base_name
from made4try.io_tcx import parse_tcx_to_rows, rows_to_dataframe
from made4try.metrics import add_metrics_minimal, estimate_vt2
from made4try.plots import make_plot_loads, make_plot_loads_dual, figure_to_html_bytes
from made4try.export_xlsx import dataframe_to_xlsx_bytes

# ---------- Auth & DB ----------
from made4try.user_auth.ui import render_auth_sidebar, require_login
from made4try.user_auth.models import init_db
from made4try.user_auth.storage import execute, query_all


# =========================================================
# Helpers
# =========================================================
def _hr_coverage_from_raw_df(df_raw) -> float:
    """HR válida = hr_bpm > 0 y no NaN."""
    try:
        if df_raw is None or "hr_bpm" not in df_raw.columns:
            return 0.0
        hr = df_raw["hr_bpm"].astype(float)
        valid = hr.notna() & (hr > 0)
        return float(valid.mean()) if len(hr) else 0.0
    except Exception:
        return 0.0


def _fmt_mmss(sec) -> str:
    """Segundos → mm:ss"""
    try:
        s = int(float(sec))
        return f"{s//60:02d}:{s%60:02d}"
    except Exception:
        return "—"


def _window_summary(df) -> str:
    """Resumen EF/DA mostrado fuera del plot."""
    if df is None or df.empty:
        return ""

    def g(c):
        return df[c].iloc[0] if c in df.columns else None

    reason = g("WIN_reason")
    if reason is not None and pd.notna(reason) and str(reason).strip():
        return f"⚠️ Ventana no válida: {reason}"

    parts = []
    if g("WIN_mode"):   parts.append(f"modo: **{g('WIN_mode')}**")
    if g("WIN_mins"):   parts.append(f"ventana: **{int(g('WIN_mins'))} min**")
    if g("WIN_signal"): parts.append(f"señal: **{g('WIN_signal')}**")
    if g("EF_win") == g("EF_win"):
        parts.append(f"EFR(rel): **{g('EF_win'):.3f}**")
    if g("DA_win_pct") == g("DA_win_pct"):
        parts.append(f"DA: **{g('DA_win_pct'):.2f}%**")
    if g("WIN_start_s") == g("WIN_start_s") and g("WIN_end_s") == g("WIN_end_s"):
        parts.append(f"rango: **{_fmt_mmss(g('WIN_start_s'))} → {_fmt_mmss(g('WIN_end_s'))}**")

    return " | ".join(parts)


# =========================================================
# Main
# =========================================================
def run():
    # ---------- Page ----------
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)

    # ---------- Auth ----------
    init_db()
    render_auth_sidebar()
    require_login()
    user = st.session_state.user

    # ---------- Header ----------
    st.title("📈 TCX → XLSX con EFR (relativo) / IF / ICR / TSS / FSS + DA por ventana")
    st.caption(
        "EFR (relativo) = (%FTP) / (%FC). "
        "DA = deriva porcentual PA:HR dentro de una ventana continua."
    )

    # ---------- Upload ----------
    uploads = st.file_uploader(
        "Sube archivos .tcx o .tcx.gz",
        type=["tcx", "gz"],
        accept_multiple_files=True,
    )

    if not uploads:
        _render_history(user["id"])
        return

    xlsx_buffers = []

    # =====================================================
    # Loop por archivo
    # =====================================================
    for idx, up in enumerate(uploads):
        st.markdown("---")
        base = clean_base_name(up.name)
        st.subheader(f"⚙️ {up.name}")

        # ---------- Inputs base ----------
        c1, c2 = st.columns(2)
        ftp  = c1.number_input("FTP (W)", min_value=1, step=1, key=f"ftp_{idx}")
        fc20 = c2.number_input("FC 20min máx (bpm)", min_value=1, step=1, key=f"fc20_{idx}")

        # ---------- Ventana EF/DA ----------
        st.markdown("#### 🧠 EF / DA — Ventana automática")
        d1, d2, d3 = st.columns(3)

        mode_label = d1.selectbox(
            "Modo",
            ["Best segment", "Decoupling valid"],
            key=f"mode_{idx}"
        )
        window_mins = d2.number_input(
            "Ventana (min)",
            min_value=5, max_value=180, value=20, step=5,
            key=f"win_{idx}"
        )
        sport_label = d3.selectbox(
            "Deporte",
            ["Auto", "Bike", "Run"],
            key=f"sport_{idx}"
        )

        window_mode = "best" if mode_label == "Best segment" else "decoupling_valid"
        sport = None if sport_label == "Auto" else sport_label.lower()

        # ---------- Procesar ----------
        if st.button("▶️ Procesar", key=f"proc_{idx}"):
            if not ftp or not fc20:
                st.warning("Ingresa FTP y FC.")
            else:
                rows = parse_tcx_to_rows(up)
                df_raw = rows_to_dataframe(rows)

                if window_mode == "decoupling_valid":
                    hr_cov = _hr_coverage_from_raw_df(df_raw)
                    if hr_cov < 0.80:
                        st.error(f"HR insuficiente ({hr_cov*100:.0f}%). Usa Best segment.")
                        continue

                df_final = add_metrics_minimal(
                    df_raw,
                    base_name=base,
                    ftp=ftp,
                    fc20=fc20,
                    window_mins=window_mins,
                    window_mode=window_mode,
                    sport=sport,
                )

                st.session_state[f"df_{idx}"] = df_final
                st.session_state[f"ftp_val_{idx}"] = ftp
                st.session_state[f"fc20_val_{idx}"] = fc20
                st.session_state[f"base_{idx}"] = base

        # ---------- Mostrar resultados ----------
        df_final = st.session_state.get(f"df_{idx}")
        if df_final is None:
            continue

        # ---------- Resumen ventana ----------
        summary = _window_summary(df_final)
        if summary:
            st.caption(summary)

        # ---------- Plots ----------
        fig1 = make_plot_loads(df_final, f"Dinámica de Carga – {base}")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = make_plot_loads_dual(df_final, f"TSS/FSS – {base}")
        st.plotly_chart(fig2, use_container_width=True)

        # ---------- Export ----------
        html = figure_to_html_bytes(fig2)
        xlsx = dataframe_to_xlsx_bytes(df_final, html_chart=html.decode("utf-8"))

        st.download_button(
            "⬇️ Descargar Excel",
            data=xlsx.getvalue(),
            file_name=f"{base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        xlsx_buffers.append((f"{base}.xlsx", xlsx))

        # ---------- KPIs ----------
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("TSS", f"{df_final['TSS_total'].iloc[0]:.1f}")
        c2.metric("FSS", f"{df_final['FSS_total'].iloc[0]:.1f}")
        c3.metric("Duración (h)", f"{df_final['elapsed_s'].iloc[-1]/3600:.2f}")
        c4.metric("Potencia media", f"{df_final['power_w'].mean():.0f} W")

        # ---------- VT2 ----------
        with st.expander("🧪 Estimador VT2 (beta)"):
            c1, c2, c3 = st.columns(3)
            win_s = c1.number_input("Ventana (s)", 60, 600, 180, key=f"vt2w_{idx}")
            ramp  = c2.number_input("Rampa mín (W/min)", 0.0, 50.0, 6.0, key=f"vt2r_{idx}")
            dhr   = c3.number_input("|dHR/dt| máx", 0.0, 5.0, 0.5, key=f"vt2d_{idx}")

            if st.button("Calcular VT2", key=f"vt2_{idx}"):
                est, _ = estimate_vt2(
                    df_final,
                    ftp=st.session_state[f"ftp_val_{idx}"],
                    hr_ftp=st.session_state[f"fc20_val_{idx}"],
                    window_s=int(win_s),
                    ramp_min_w_per_min=float(ramp),
                    dhr_flat_bpm_per_min=float(dhr),
                )

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("P@VT2", f"{est['vt2_power_w']} W")
                k2.metric("HR@VT2", f"{est['vt2_hr_bpm']} bpm")
                k3.metric("EFF", f"{est['vt2_eff']}")
                k4.metric("Confianza", f"{est['confidence_0_1']}")

        # ---------- Save history ----------
        try:
            execute(
                """
                INSERT INTO workouts
                (user_id, file_name, date, tss_total, fss_total, duration_h,
                 avg_power, avg_hr, efr_avg, icr_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"], base,
                    df_final["fecha"].iloc[0],
                    float(df_final["TSS_total"].iloc[0]),
                    float(df_final["FSS_total"].iloc[0]),
                    float(df_final["elapsed_s"].iloc[-1] / 3600),
                    float(df_final["power_w"].mean()),
                    float(df_final["hr_bpm"].mean()),
                    float(df_final["EFR"].mean()),
                    float(df_final["ICR"].mean()),
                ),
            )
            st.success("💾 Guardado en historial.")
        except Exception:
            pass

    # ---------- ZIP ----------
    if len(xlsx_buffers) > 1:
        zip_bio = BytesIO()
        with zipfile.ZipFile(zip_bio, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn, fb in xlsx_buffers:
                zf.writestr(fn, fb.getvalue())
        st.download_button("📦 Descargar ZIP", zip_bio.getvalue(), "tcx_resultados.zip")

    _render_history(user["id"])


def _render_history(user_id: int):
    try:
        rows = query_all(
            """
            SELECT date, file_name, tss_total, fss_total, duration_h,
                   avg_power, avg_hr, efr_avg, icr_avg, created_at
            FROM workouts
            WHERE user_id = ?
            ORDER BY COALESCE(date, created_at) DESC
            """,
            (user_id,),
        )
        if rows:
            st.markdown("---")
            st.subheader("📜 Historial")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
    except Exception:
        pass


if __name__ == "__main__":
    run()
