# =========================
# made4try/app.py — Punto de entrada Streamlit
# =========================
import streamlit as st
from io import BytesIO
import zipfile
import traceback  # para ver el stacktrace en la UI si algo falla

from . import config  # por si quieres reflejar el valor elegido globalmente
from .config import PAGE_TITLE, PAGE_ICON, LAYOUT, DISPLAY_SMOOTH_SECONDS
from .utils import clean_base_name
from .io_tcx import parse_tcx_to_rows, rows_to_dataframe
from .metrics import add_metrics_minimal
from .plots import make_plot_loads, make_plot_loads_dual, figure_to_html_bytes
from .export_xlsx import dataframe_to_xlsx_bytes


def run():
    # --- Config y encabezado ---
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)
    st.title("📈 TCX → XLSX con EFR / IF / ICR / TSS / FSS")
    st.write(
        "Sube uno o varios **.tcx** o **.tcx.gz**. "
        "Para cada archivo ingresa **FTP (W)** y **FC_20min_max (bpm)**.\n\n"
        "**ICR = IF ÷ EFR**.  TSS=Σ(IF²·Δt_h·100), FSS=Σ(ICR²·Δt_h·100)."
    )

    # --- Sidebar: controles de visualización ---
    with st.sidebar:
        st.header("⚙️ Configuración de visualización")
        smooth_secs = st.slider(
            "Suavizado de Potencia/FC (s)",
            1, 30, DISPLAY_SMOOTH_SECONDS,
            help="Ventana en segundos para suavizar Potencia y Frecuencia Cardíaca en los gráficos."
        )
        # (opcional) reflejar globalmente el valor elegido
        config.DISPLAY_SMOOTH_SECONDS = int(smooth_secs)

    # --- Uploader ---
    uploads = st.file_uploader(
        "Sube tus archivos (puedes seleccionar varios)",
        type=["tcx", "gz"],
        accept_multiple_files=True,
        key="uploader_main",
    )

    if not uploads:
        st.info("⬆️ Carga archivos para empezar.")
        return

    # --- Procesamiento por archivo ---
    xlsx_buffers = []
    for idx, up in enumerate(uploads):
        st.markdown("---")
        base = clean_base_name(up.name)
        st.subheader(f"⚙️ Parámetros para: `{up.name}`")

        c1, c2 = st.columns(2)
        ftp = c1.number_input(
            f"FTP (W) – {up.name}", min_value=1, step=1, key=f"ftp_{idx}"
        )
        fc20 = c2.number_input(
            f"FC_20min_max (bpm) – {up.name}", min_value=1, step=1, key=f"fc20_{idx}"
        )

        avanzar = st.button(f"▶️ Procesar {up.name}", key=f"proc_{idx}")

        if not avanzar:
            continue

        if not (ftp and fc20):
            st.warning("⚠️ Ingresa FTP y FC_20min_max para continuar.")
            continue

        with st.spinner(f"🔄 Procesando {up.name}..."):
            try:
                # Parseo + métricas
                rows = parse_tcx_to_rows(up)
                df_raw = rows_to_dataframe(rows)

                # PASO CLAVE: pasar smooth_secs al cálculo para que plots use power_smooth/hr_smooth
                df_final = add_metrics_minimal(
                    df_raw, base_name=base, ftp=ftp, fc20=fc20, smooth_secs=int(smooth_secs)
                )

                # ---------- Gráfica base ----------
                st.subheader("📊 Análisis con Señales Base")
                fig1 = make_plot_loads(
                    df_final, title=f"Dinámica de Carga – {base}", show_base=True
                )
                st.plotly_chart(fig1, use_container_width=True)
                html1 = figure_to_html_bytes(fig1)
                st.download_button(
                    "⬇️ Descargar gráfica completa (HTML)",
                    data=html1,
                    file_name=f"{base}_analisis_completo.html",
                    mime="text/html",
                    key=f"html_full_{idx}",
                )

                # ---------- Gráfica dual ----------
                st.subheader("📈 Comparación: Acumulados vs. Segundo a Segundo")
                fig2 = make_plot_loads_dual(
                    df_final, title=f"TSS/FSS: Acumulado vs. Dinámico – {base}"
                )
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

                # ---------- Excel con “gráfica embebida” ----------
                xlsx_bio = dataframe_to_xlsx_bytes(
                    df_final, html_chart=html2.decode("utf-8")
                )
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

                # ---------- Métricas totales ----------
                tss_total = float(df_final["TSS_total"].iloc[0])
                fss_total = float(df_final["FSS_total"].iloc[0])
                c3, c4 = st.columns(2)
                c3.metric("TSS Total", f"{tss_total:.1f}")
                c4.metric("FSS Total", f"{fss_total:.1f}")

            except Exception as e:
                # Mensaje legible + traceback completo para diagnóstico
                st.error(f"❌ Error en {up.name}: {e}")
                st.code(traceback.format_exc())

    # --- ZIP con todos los Excel (si hay más de uno) ---
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
