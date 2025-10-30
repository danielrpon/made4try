# made4try/app.py — Punto de entrada Streamlit
import streamlit as st
from io import BytesIO
import zipfile

# --- Auth & DB ---
from user_auth.ui import render_auth_sidebar, require_login, is_admin
from user_auth.models import init_db
from user_auth.storage import execute

# --- App base ---
from .config import PAGE_TITLE, PAGE_ICON, LAYOUT
from .utils import clean_base_name
from .io_tcx import parse_tcx_to_rows, rows_to_dataframe
from .metrics import add_metrics_minimal
from .plots import make_plot_loads, make_plot_loads_dual, figure_to_html_bytes
from .export_xlsx import dataframe_to_xlsx_bytes


def run():
    # ------------------- Configuración de página -------------------
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)

    # ------------------- Autenticación -------------------
    init_db()                 # asegura tablas (idempotente)
    render_auth_sidebar()     # login / signup / logout en el sidebar
    require_login()           # bloquea si no hay sesión
    user = st.session_state.user  # dict: {'id','email','name','role',...}

    # ------------------- Encabezado UI -------------------
    st.title("📈 TCX → XLSX con EFR / IF / ICR / TSS / FSS")
    st.caption(
        "Sube **.tcx** o **.tcx.gz**. Ingresa **FTP (W)** y **FC_20min_max (bpm)**. "
        "**ICR = IF ÷ EFR**.  TSS=Σ(IF²·Δt_h·100), FSS=Σ(ICR²·Δt_h·100)."
    )

    # ------------------- Uploader -------------------
    uploads = st.file_uploader(
        "Sube tus archivos (puedes seleccionar varios)",
        type=["tcx", "gz"],
        accept_multiple_files=True,
        key="uploader_main",
    )

    if not uploads:
        st.info("⬆️ Carga uno o más archivos para comenzar.")
        return

    # ------------------- Procesamiento -------------------
    xlsx_buffers = []

    for idx, up in enumerate(uploads):
        st.markdown("---")
        base = clean_base_name(up.name)
        st.subheader(f"⚙️ Parámetros para: `{up.name}`")

        c1, c2 = st.columns(2)
        ftp = c1.number_input(f"FTP (W) – {up.name}", min_value=1, step=1, key=f"ftp_{idx}")
        fc20 = c2.number_input(f"FC_20min_max (bpm) – {up.name}", min_value=1, step=1, key=f"fc20_{idx}")

        if not st.button(f"▶️ Procesar {up.name}", key=f"proc_{idx}"):
            continue

        if not (ftp and fc20):
            st.warning("⚠️ Ingresa FTP y FC_20min_max para continuar.")
            continue

        with st.spinner(f"🔄 Procesando {up.name}..."):
            try:
                # Parseo + métricas
                rows = parse_tcx_to_rows(up)
                df_raw = rows_to_dataframe(rows)
                df_final = add_metrics_minimal(df_raw, base_name=base, ftp=ftp, fc20=fc20)

                # Gráfica base
                st.subheader("📊 Análisis con Señales Base")
                fig1 = make_plot_loads(df_final, title=f"Dinámica de Carga – {base}", show_base=True)
                st.plotly_chart(fig1, use_container_width=True)
                html1 = figure_to_html_bytes(fig1)
                st.download_button(
                    "⬇️ Descargar gráfica completa (HTML)",
                    data=html1,
                    file_name=f"{base}_analisis_completo.html",
                    mime="text/html",
                    key=f"html_full_{idx}",
                )

                # Gráfica dual
                st.subheader("📈 Comparación: Acumulados vs. Segundo a Segundo")
                fig2 = make_plot_loads_dual(df_final, title=f"TSS/FSS: Acumulado vs. Dinámico – {base}")
                st.plotly_chart(fig2, use_container_width=True)
                html2 = figure_to_html_bytes(fig2)
                st.download_button(
                    "⬇️ Descargar gráfica dinámica (HTML)",
                    data=html2,
                    file_name=f"{base}_dinamica_detallada.html",
                    mime="text/html",
                    key=f"html_dyn_{idx}",
                )

                st.info("💡 Arriba: acumulados + promedios móviles. Abajo: incrementos instantáneos.")

                # Excel con “gráfica embebida” (preview + texto)
                xlsx_bio = dataframe_to_xlsx_bytes(df_final, html_chart=html2.decode("utf-8"))
                out_name = f"{base}.xlsx"
                xlsx_buffers.append((out_name, xlsx_bio))
                st.success(f"✅ {out_name} listo (con gráfica embebida)")
                st.download_button(
                    f"⬇️ Descargar {out_name}",
                    data=xlsx_bio.getvalue(),
                    file_name=out_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"xlsx_{idx}",
                )

                # Métricas Totales en UI
                col_a, col_b, col_c, col_d = st.columns(4)
                tss_total = float(df_final["TSS_total"].iloc[0])
                fss_total = float(df_final["FSS_total"].iloc[0])
                duration_h = float(df_final["elapsed_s"].iloc[-1] / 3600.0)
                avg_power = float(df_final["power_w"].mean())
                col_a.metric("TSS Total", f"{tss_total:.1f}")
                col_b.metric("FSS Total", f"{fss_total:.1f}")
                col_c.metric("Duración (h)", f"{duration_h:.2f}")
                col_d.metric("Potencia Media (W)", f"{avg_power:.1f}")

                # --- Guardar resumen del entrenamiento en BD (no bloqueante) ---
                try:
                    avg_hr   = float(df_final["hr_bpm"].mean()) if "hr_bpm" in df_final.columns else None
                    efr_avg  = float(df_final["EFR"].mean()) if "EFR" in df_final.columns else None
                    icr_avg  = float(df_final["ICR"].mean()) if "ICR" in df_final.columns else None
                    date_val = df_final["fecha"].iloc[0] if "fecha" in df_final.columns else None

                    execute(
                        """
                        INSERT INTO workouts
                          (user_id, file_name, date, tss_total, fss_total, duration_h,
                           avg_power, avg_hr, efr_avg, icr_avg)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user["id"], base, date_val, tss_total, fss_total, duration_h,
                         avg_power, avg_hr, efr_avg, icr_avg),
                    )
                    st.success("💾 Entrenamiento guardado en tu historial.")
                except Exception as e:
                    st.warning(f"Guardado del historial falló (no bloqueante): {e}")

            except Exception as e:
                st.error(f"❌ Error en {up.name}: {e}")

    # ------------------- ZIP con todos los Excel -------------------
    if len(xlsx_buffers) > 1:
        zip_bio = BytesIO()
        with zipfile.ZipFile(zip_bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname, fb in xlsx_buffers:
                zf.writestr(fname, fb.getvalue())
        zip_bio.seek(0)
        st.download_button(
            "📦 Descargar todos (.zip)",
            data=zip_bio.getvalue(),
            file_name="tcx_convertidos.zip",
            mime="application/zip",
            key="zip_all",
        )

    # ------------------- (Opcional) Historial del usuario -------------------
    try:
        rows = query_all(
            """
            SELECT date, file_name, tss_total, fss_total, duration_h,
                   avg_power, avg_hr, efr_avg, icr_avg, created_at
            FROM workouts
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user["id"],),
        )
        if rows:
            import pandas as pd
            st.markdown("---")
            st.subheader("📜 Historial de entrenos")
            st.dataframe(pd.DataFrame([dict(r) for r in rows]), use_container_width=True)
    except Exception as e:
        st.warning(f"No fue posible cargar el historial: {e}")


# Streamlit Cloud/CLI entry
if __name__ == "__main__":
    run()