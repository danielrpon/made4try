# streamlit_app.py (fino)
from made4try.app import * # o simplemente: ejecuta `streamlit run -m made4try.app`


# """
# Aplicación Streamlit para convertir archivos TCX en tablas Excel con métricas
# de entrenamiento (EFR, IF, ICR) e indicadores de carga (TSS/FSS).

# Esta versión incorpora una interfaz más profesional y optimizada:

# * Utiliza un panel lateral para la subida de archivos y parámetros globales.
# * Agrupa la introducción de FTP y FC 20 minutos por archivo en expansores
#   desplegables, evitando saturar la pantalla principal.
# * Permite ajustar el tamaño de la ventana del promedio móvil de los
#   incrementos (por defecto 10 s) con un control deslizante.
# * Emplea `st.cache_data` para almacenar la lectura y conversión de los
#   archivos, acelerando el procesamiento cuando se recargan.
# * Muestra indicadores clave (TSS total, FSS total y duración) mediante
#   `st.metric` al completar el cálculo de cada archivo.
# * Organiza la visualización de resultados en pestañas: tabla de datos,
#   gráfica con señales base y gráfica comparativa de incrementos vs.
#   acumulados.
# * Permite descargar cada tabla como Excel con la gráfica HTML embebida y
#   todas las tablas en un archdivo ZIP si se procesan varios archivos.

# Para personalizar aún más el aspecto del aplicativo, se puede crear un
# archivo `.streamlit/config.toml` con una sección `[theme]` donde se
# definan colores, fuentes y bordes. La documentación oficial de Streamlit
# detalla las opciones disponibles:contentReference[oaicite:0]{index=0}.
# """

# import streamlit as st
# import pandas as pd
# import xml.etree.ElementTree as ET
# from io import TextIOWrapper, BytesIO, StringIO
# import gzip
# import zipfile
# from datetime import datetime
# import plotly.graph_objects as go
# from plotly.subplots import make_subplots

# # Configuración de la página y estilo básico
# st.set_page_config(
#     page_title="TCX → XLSX (EFR/IF/ICR/TSS/FSS)",
#     page_icon="📈",
#     layout="wide",
# )

# # Estilos adicionales mediante Markdown y CSS (puede ajustarse al gusto)
# st.markdown(
#     """
#     <style>
#     /* Encabezado principal */
#     .title-wrapper {
#         font-family: 'Montserrat', sans-serif;
#         color: #2E3A59;
#     }
#     /* Barras separadoras */
#     hr {margin-top: 1rem; margin-bottom: 1rem; border-color: #E0E4EC;}
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# # Namespaces XML para TCX
# NS = {
#     "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
#     "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
#     "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
# }

# # Función utilitaria para limpiar el nombre base del archivo (sin extensiones).
# def clean_base_name(name: str) -> str:
#     """
#     Elimina las extensiones .gz y .tcx del nombre de archivo para usarlo como
#     nombre base en las salidas (por ejemplo, en los nombres de Excel o HTML).
#     """
#     base = name
#     if base.lower().endswith(".gz"):
#         base = base[:-3]
#     if base.lower().endswith(".tcx"):
#         base = base[:-4]
#     return base

# # -----------------------------------------------------------------------------
# # Utilidades de parseo y conversión
# # Estas funciones se cachean para evitar reprocesar los mismos archivos.

# def parse_iso8601_z(ts: str):
#     """Parsea una cadena ISO 8601 que puede terminar en Z (UTC)."""
#     try:
#         if ts and ts.endswith("Z"):
#             return datetime.fromisoformat(ts.replace("Z", "+00:00"))
#         return datetime.fromisoformat(ts) if ts else None
#     except Exception:
#         return None

# def get_text(_elem, paths):
#     """Extrae el texto de la primera coincidencia de rutas XPath en un elemento XML.

#     El parámetro `elem` está precedido por un guion bajo para que Streamlit ignore
#     su hash cuando se usa en funciones cacheadas. Esta convención se recomienda
#     cuando se pasan objetos no hashables a funciones decoradas por Streamlit.
#     """
#     for p in paths:
#         node = _elem.find(p, NS)
#         if node is not None and node.text:
#             return node.text.strip()
#     return None

# def to_float(x):
#     try:
#         return float(x)
#     except (TypeError, ValueError):
#         return None

# def to_int(x):
#     try:
#         return int(float(x))
#     except (TypeError, ValueError):
#         return None

# def open_maybe_gzip_bytes(uploaded_file):
#     """Devuelve un manejador de texto UTF‑8 para un archivo TCX o TCX.GZ subido."""
#     name = uploaded_file.name.lower()
#     if name.endswith(".gz"):
#         gz = gzip.GzipFile(fileobj=BytesIO(uploaded_file.getvalue()), mode="rb")
#         return TextIOWrapper(gz, encoding="utf-8")
#     else:
#         return TextIOWrapper(BytesIO(uploaded_file.getvalue()), encoding="utf-8")

# @st.cache_data(show_spinner=False)
# def parse_tcx_to_rows(uploaded_file):
#     """Parsea un archivo TCX y devuelve una lista de diccionarios por trackpoint."""
#     f = open_maybe_gzip_bytes(uploaded_file)
#     tree = ET.parse(f)
#     root = tree.getroot()
#     rows = []
#     first_ts = None

#     for act in root.findall(".//tcx:Activities/tcx:Activity", NS):
#         sport = act.get("Sport")
#         for li, lap in enumerate(act.findall("tcx:Lap", NS), start=1):
#             for track in lap.findall("tcx:Track", NS):
#                 for ti, tp in enumerate(track.findall("tcx:Trackpoint", NS), start=1):
#                     ts_txt = get_text(tp, ["tcx:Time"])
#                     ts = parse_iso8601_z(ts_txt) if ts_txt else None
#                     if ts and first_ts is None:
#                         first_ts = ts
#                     elapsed = (ts - first_ts).total_seconds() if (ts and first_ts) else None

#                     lat = to_float(get_text(tp, ["tcx:Position/tcx:LatitudeDegrees"]))
#                     lon = to_float(get_text(tp, ["tcx:Position/tcx:LongitudeDegrees"]))
#                     alt = to_float(get_text(tp, ["tcx:AltitudeMeters"]))
#                     dist = to_float(get_text(tp, ["tcx:DistanceMeters"]))
#                     hr = to_int(get_text(tp, ["tcx:HeartRateBpm/tcx:Value"]))
#                     cad = to_int(get_text(tp, ["tcx:Cadence"]))
#                     speed_mps = to_float(
#                         get_text(tp, [
#                             "tcx:Extensions/ns3:TPX/ns3:Speed",
#                             "tcx:Extensions/ns2:TPX/ns2:Speed",
#                         ])
#                     )
#                     watts = to_float(
#                         get_text(tp, [
#                             "tcx:Extensions/ns3:TPX/ns3:Watts",
#                             "tcx:Extensions/ns2:TPX/ns2:Watts",
#                         ])
#                     )
#                     run_spm = to_int(
#                         get_text(tp, [
#                             "tcx:Extensions/ns3:TPX/ns3:RunCadence",
#                             "tcx:Extensions/ns2:TPX/ns2:RunCadence",
#                         ])
#                     )
#                     if cad is None:
#                         cad = to_int(
#                             get_text(tp, [
#                                 "tcx:Extensions/ns3:TPX/ns3:Cadence",
#                                 "tcx:Extensions/ns2:TPX/ns2:Cadence",
#                             ])
#                         )
#                     speed_kmh = speed_mps * 3.6 if speed_mps is not None else None

#                     rows.append({
#                         "activity_sport": sport,
#                         "lap_index": li,
#                         "trackpoint_index": ti,
#                         "time_utc": ts.isoformat() if ts else None,
#                         "elapsed_s": round(elapsed, 3) if elapsed is not None else None,
#                         "latitude_deg": lat,
#                         "longitude_deg": lon,
#                         "altitude_m": alt,
#                         "distance_m": dist,
#                         "speed_mps": speed_mps,
#                         "speed_kmh": round(speed_kmh, 3) if speed_kmh is not None else None,
#                         "hr_bpm": hr,
#                         "cadence_rpm": cad,
#                         "run_cadence_spm": run_spm,
#                         "power_w": watts,
#                     })
#     return rows

# @st.cache_data(show_spinner=False)
# def rows_to_dataframe(rows) -> pd.DataFrame:
#     """Convierte la lista de dicts en DataFrame y tipifica las columnas."""
#     from pandas import to_datetime
#     if not rows:
#         rows = [{
#             "activity_sport": None, "lap_index": None, "trackpoint_index": None,
#             "time_utc": None, "elapsed_s": None, "latitude_deg": None,
#             "longitude_deg": None, "altitude_m": None, "distance_m": None,
#             "speed_mps": None, "speed_kmh": None, "hr_bpm": None,
#             "cadence_rpm": None, "run_cadence_spm": None, "power_w": None
#         }]
#     df = pd.DataFrame(rows)
#     if "time_utc" in df.columns:
#         dt = to_datetime(df["time_utc"], errors="coerce", utc=True).dt.tz_convert(None)
#         df["time_utc"] = dt
#     float_cols = ["elapsed_s", "latitude_deg", "longitude_deg", "altitude_m",
#                   "distance_m", "speed_mps", "speed_kmh", "power_w"]
#     int_cols = ["hr_bpm", "cadence_rpm", "run_cadence_spm"]
#     for c in float_cols:
#         if c in df.columns:
#             df[c] = pd.to_numeric(df[c], errors="coerce")
#     for c in int_cols:
#         if c in df.columns:
#             df[c] = pd.to_numeric(df[c], errors="coerce", downcast="integer")
#     if "time_utc" in df.columns:
#         df = df.sort_values("time_utc").reset_index(drop=True)
#     return df

# # -----------------------------------------------------------------------------
# # Cálculo de métricas y cargas

# def add_metrics_minimal(df: pd.DataFrame, base_name: str, ftp: float, fc20: float, window: int) -> pd.DataFrame:
#     """
#     Devuelve un DataFrame con columnas mínimas y métricas calculadas.

#     Se calculan %FTP, %FC_rel, EFR, IF, ICR, intervalos de tiempo, incrementos
#     instantáneos de TSS y FSS, su promedio móvil (ventana configurable) y las
#     cargas acumuladas. Además se añaden columnas TSS_total y FSS_total con los
#     valores finales para toda la sesión (solo en la primera fila).
#     """
#     df = df.copy()
#     fecha = None
#     if "time_utc" in df.columns and pd.api.types.is_datetime64_any_dtype(df["time_utc"]):
#         if df["time_utc"].notna().any():
#             fecha = df["time_utc"].dropna().iloc[0].date()
#     df["fecha"] = fecha.isoformat() if fecha else None
#     df["documento"] = base_name
#     keep = {
#         "fecha": df.get("fecha"),
#         "documento": df.get("documento"),
#         "elapsed_s": pd.to_numeric(df.get("elapsed_s"), errors="coerce"),
#         "power_w": pd.to_numeric(df.get("power_w"), errors="coerce"),
#         "hr_bpm": pd.to_numeric(df.get("hr_bpm"), errors="coerce"),
#         "speed_kmh": pd.to_numeric(df.get("speed_kmh"), errors="coerce"),
#     }
#     m = pd.DataFrame(keep)
#     ftp = float(ftp)
#     fc20 = float(fc20)
#     power = m["power_w"].fillna(0.0)
#     hr = m["hr_bpm"].astype(float).replace({0.0: pd.NA})
#     pct_ftp = (power / ftp) * 100.0
#     pct_fc = (hr / fc20) * 100.0
#     efr = pct_ftp / pct_fc
#     intensity_factor = power / ftp
#     icr = intensity_factor / efr
#     # Intervalos de tiempo
#     el = m["elapsed_s"].astype(float)
#     dt_s = el.diff()
#     if dt_s.notna().sum() >= 1:
#         first_dt = dt_s.dropna().iloc[0]
#         try:
#             first_dt = float(first_dt)
#         except Exception:
#             first_dt = 1.0
#         if not (first_dt > 0):
#             first_dt = 1.0
#     else:
#         first_dt = 1.0
#     dt_s = dt_s.fillna(first_dt).clip(lower=0.0)
#     dt_h = dt_s / 3600.0
#     tss_inc = (intensity_factor ** 2) * dt_h * 100.0
#     fss_inc = (icr ** 2) * dt_h * 100.0
#     tss_cum = tss_inc.cumsum()
#     fss_cum = fss_inc.cumsum()
#     # Promedios móviles
#     window_n = max(1, int(window))
#     tss_inc_ma = tss_inc.rolling(window=window_n, min_periods=1).mean()
#     fss_inc_ma = fss_inc.rolling(window=window_n, min_periods=1).mean()
#     # Totales
#     tss_total = tss_cum.iloc[-1] if len(tss_cum) > 0 else 0.0
#     fss_total = fss_cum.iloc[-1] if len(fss_cum) > 0 else 0.0
#     # Asignar
#     m["pct_ftp"] = pct_ftp
#     m["pct_fc_rel"] = pct_fc
#     m["EFR"] = efr
#     m["IF"] = intensity_factor
#     m["ICR"] = icr
#     m["dt_s"] = dt_s
#     m["TSS_inc"] = tss_inc
#     m["FSS_inc"] = fss_inc
#     m["TSS_inc_ma"] = tss_inc_ma
#     m["FSS_inc_ma"] = fss_inc_ma
#     m["TSS"] = tss_cum
#     m["FSS"] = fss_cum
#     m["TSS_total"] = pd.NA
#     m["FSS_total"] = pd.NA
#     m.loc[0, "TSS_total"] = tss_total
#     m.loc[0, "FSS_total"] = fss_total
#     return m

# # -----------------------------------------------------------------------------
# # Exportación y visualización

# def dataframe_to_xlsx_bytes(df: pd.DataFrame, html_chart: str = None, sheet_name: str = "DATA") -> BytesIO:
#     """Exporta un DataFrame a un buffer XLSX en memoria con gráfica HTML embebida."""
#     bio = BytesIO()
#     with pd.ExcelWriter(bio, engine="openpyxl") as xw:
#         df.to_excel(xw, index=False, sheet_name=sheet_name)
#         ws = xw.book[sheet_name]
#         from openpyxl.utils import get_column_letter
#         for i, col in enumerate(df.columns, start=1):
#             width = 12
#             if col in ("fecha", "documento"):
#                 width = 18
#             if col in ("elapsed_s", "power_w", "hr_bpm", "speed_kmh", "dt_s"):
#                 width = 12
#             if col in ("pct_ftp", "pct_fc_rel", "EFR", "IF", "ICR",
#                        "TSS_inc", "FSS_inc", "TSS_inc_ma", "FSS_inc_ma",
#                        "TSS", "FSS", "TSS_total", "FSS_total"):
#                 width = 14
#             ws.column_dimensions[get_column_letter(i)].width = width
#         if html_chart:
#             # Crear hoja para la gráfica
#             chart_sheet = xw.book.create_sheet("Gráficas")
#             chart_sheet["A1"] = "Gráfica Interactiva"
#             chart_sheet["A1"].font = chart_sheet["A1"].font.copy(bold=True, size=14)
#             chart_sheet["A3"] = "Para ver la gráfica completa, abre el archivo HTML descargado."
#             chart_sheet["A3"].font = chart_sheet["A3"].font.copy(italic=True)
#             chart_sheet["A5"] = "Vista previa (HTML):"
#             preview_text = html_chart[:500] + "..." if len(html_chart) > 500 else html_chart
#             chart_sheet["A6"] = preview_text
#             chart_sheet["A6"].alignment = chart_sheet["A6"].alignment.copy(wrap_text=True)
#             chart_sheet.column_dimensions['A'].width = 100
#     bio.seek(0)
#     return bio

# def make_plot_loads(df: pd.DataFrame, title: str, show_base: bool = True) -> go.Figure:
#     """Crea una figura de Plotly con TSS y FSS acumulados, y señales base opcionales."""
#     t = df["elapsed_s"]
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines"))
#     fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines"))
#     if show_base:
#         if "power_w" in df.columns:
#             fig.add_trace(go.Scatter(x=t, y=df["power_w"], name="Potencia (W)", mode="lines", yaxis="y2"))
#         if "hr_bpm" in df.columns:
#             fig.add_trace(go.Scatter(x=t, y=df["hr_bpm"], name="FC (bpm)", mode="lines", yaxis="y3"))
#     layout = dict(
#         title=title,
#         xaxis=dict(title="Tiempo (s)"),
#         yaxis=dict(title="Carga acumulada (TSS/FSS)", rangemode="tozero"),
#         yaxis2=dict(title="Potencia (W)", overlaying="y", side="right", position=1.0, showgrid=False),
#         yaxis3=dict(title="FC (bpm)", overlaying="y", side="right", position=0.98, showgrid=False),
#         legend=dict(orientation="h", x=0, y=1.12),
#         template="plotly_white",
#         margin=dict(l=60, r=80, t=70, b=50),
#     )
#     fig.update_layout(**layout)
#     return fig

# def make_plot_loads_dual(df: pd.DataFrame, title: str) -> go.Figure:
#     """Crea una figura de Plotly con dos subplots: acumulados y incrementos."""
#     t = df["elapsed_s"]
#     fig = make_subplots(
#         rows=2, cols=1,
#         subplot_titles=(
#             "Carga Acumulada y Promedio Móvil",
#             "Incrementos Instantáneos",
#         ),
#         vertical_spacing=0.12,
#         row_heights=[0.6, 0.4],
#     )
#     # Acumulados y promedios móviles
#     fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines", line=dict(color="#1f77b4", width=2.5)), row=1, col=1)
#     fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines", line=dict(color="#ff7f0e", width=2.5)), row=1, col=1)
#     fig.add_trace(go.Scatter(x=t, y=df["TSS_inc_ma"], name="ΔTSS (MA)", mode="lines", line=dict(color="#2ca02c", width=1.5, dash="dash")), row=1, col=1)
#     fig.add_trace(go.Scatter(x=t, y=df["FSS_inc_ma"], name="ΔFSS (MA)", mode="lines", line=dict(color="#d62728", width=1.5, dash="dash")), row=1, col=1)
#     # Incrementos instantáneos
#     fig.add_trace(go.Scatter(x=t, y=df["TSS_inc"], name="ΔTSS (inst)", mode="lines", line=dict(color="#2ca02c", width=1)), row=2, col=1)
#     fig.add_trace(go.Scatter(x=t, y=df["FSS_inc"], name="ΔFSS (inst)", mode="lines", line=dict(color="#d62728", width=1)), row=2, col=1)
#     fig.update_xaxes(title_text="Tiempo (s)", row=2, col=1)
#     fig.update_xaxes(title_text="", row=1, col=1)
#     fig.update_yaxes(title_text="Incrementos", row=2, col=1)
#     fig.update_layout(
#         title=dict(text=title, x=0.5, xanchor="center"),
#         showlegend=True,
#         legend=dict(orientation="h", x=0, y=-0.12, xanchor="left"),
#         template="plotly_white",
#         height=900,
#         margin=dict(l=70, r=80, t=80, b=60),
#     )
#     return fig

# def render_results(df: pd.DataFrame, base_name: str, window: int, key_prefix: str) -> str:
#     """
#     Muestra indicadores, gráficos y tabla en pestañas y ofrece descargas.
#     Devuelve el HTML de la gráfica dual para embeber en Excel.
#     """
#     # Métricas principales
#     col1, col2, col3 = st.columns(3)
#     tss_total = df["TSS_total"].iloc[0]
#     fss_total = df["FSS_total"].iloc[0]
#     duration_h = df["elapsed_s"].iloc[-1] / 3600.0 if len(df) > 0 else 0.0
#     col1.metric("TSS Total", f"{tss_total:.1f}")
#     col2.metric("FSS Total", f"{fss_total:.1f}")
#     col3.metric("Duración (h)", f"{duration_h:.2f}")
#     # Pestañas para mostrar resultados
#     tabs = st.tabs(["Tabla", "Gráfica acumulada", "Gráfica dinámica"])
#     with tabs[0]:
#         st.dataframe(df)
#     with tabs[1]:
#         fig1 = make_plot_loads(df, title=f"Dinámica de Carga – {base_name}", show_base=True)
#         st.plotly_chart(fig1, use_container_width=True, key=f"{key_prefix}_plot1")
#         html_buf1 = StringIO()
#         fig1.write_html(html_buf1, include_plotlyjs="cdn", full_html=True)
#         html_bytes1 = html_buf1.getvalue().encode("utf-8")
#         file_html1 = f"{base_name}_acumulado.html"
#         st.download_button(
#             label="Descargar gráfica acumulada (HTML)",
#             data=html_bytes1,
#             file_name=file_html1,
#             mime="text/html",
#             key=f"{key_prefix}_html_acum",
#         )
#     with tabs[2]:
#         fig2 = make_plot_loads_dual(df, title=f"TSS/FSS: Acumulado vs. Incrementos – {base_name}")
#         st.plotly_chart(fig2, use_container_width=True, key=f"{key_prefix}_plot2")
#         html_buf2 = StringIO()
#         fig2.write_html(html_buf2, include_plotlyjs="cdn", full_html=True)
#         html_bytes2 = html_buf2.getvalue().encode("utf-8")
#         file_html2 = f"{base_name}_dinamica.html"
#         st.download_button(
#             label="Descargar gráfica dinámica (HTML)",
#             data=html_bytes2,
#             file_name=file_html2,
#             mime="text/html",
#             key=f"{key_prefix}_html_dyn",
#         )
#     return html_bytes2.decode("utf-8")

# # -----------------------------------------------------------------------------
# # Interfaz de usuario principal

# def main():
#     st.markdown("<div class='title-wrapper'><h1>📈 TCX → XLSX con EFR / IF / ICR / TSS / FSS</h1></div>", unsafe_allow_html=True)
#     st.write(
#         """
#         Esta aplicación convierte archivos TCX en hojas de cálculo Excel con
#         métricas de entrenamiento y gráficas de carga. Ingresa tu FTP y la
#         frecuencia cardiaca media de tus mejores 20 minutos (últimos 90 días) para
#         cada archivo. Puedes ajustar el tamaño de la ventana del promedio móvil
#         para suavizar los incrementos de carga.
#         """
#     )
#     # Panel lateral: carga de archivos y configuración
#     with st.sidebar:
#         st.header("📂 Cargar archivos TCX")
#         uploads = st.file_uploader(
#             "Selecciona uno o varios archivos .tcx o .tcx.gz",
#             type=["tcx", "gz"],
#             accept_multiple_files=True,
#             key="uploader_main",
#         )
#         st.header("⚙️ Configuración")
#         window = st.slider(
#             "Ventana promedio móvil (nº de muestras)",
#             min_value=5,
#             max_value=50,
#             value=10,
#             step=1,
#             help="Número de muestras utilizadas para suavizar ΔTSS/ΔFSS",
#         )
#         st.markdown(
#             """
#             **Tema:** Para ajustar los colores, tipografías y bordes de la app
#             puedes crear un archivo `.streamlit/config.toml` con la sección
#             `[theme]` (ver documentación de Streamlit):contentReference[oaicite:1]{index=1}.
#             """
#         )

#     if uploads:
#         xlsx_buffers = []
#         for idx, up in enumerate(uploads):
#             base = clean_base_name(up.name)
#             key_prefix = f"file_{idx}"
#             with st.expander(f"⚙️ Parámetros para {up.name}", expanded=False):
#                 ftp_val = st.number_input(
#                     f"FTP (W) para {up.name}",
#                     min_value=1,
#                     step=1,
#                     key=f"{key_prefix}_ftp",
#                 )
#                 fc_val = st.number_input(
#                     f"FC_20min_max (bpm) para {up.name}",
#                     min_value=1,
#                     step=1,
#                     key=f"{key_prefix}_fc20",
#                 )
#                 process = st.button(
#                     f"Procesar {up.name}",
#                     key=f"{key_prefix}_procesar",
#                 )
#             if process:
#                 if not (ftp_val and fc_val):
#                     st.warning("Debes ingresar valores de FTP y FC_20min_max.")
#                 else:
#                     with st.spinner(f"Procesando {up.name}..."):
#                         try:
#                             rows = parse_tcx_to_rows(up)
#                             df_raw = rows_to_dataframe(rows)
#                             df_final = add_metrics_minimal(df_raw, base_name=base, ftp=ftp_val, fc20=fc_val, window=window)
#                             html_chart = render_results(df_final, base_name=base, window=window, key_prefix=key_prefix)
#                             out_name = f"{base}.xlsx"
#                             xlsx_bio = dataframe_to_xlsx_bytes(df_final, html_chart=html_chart, sheet_name="DATA")
#                             xlsx_buffers.append((out_name, xlsx_bio))
#                             st.success(f"{out_name} listo para descargar")
#                             st.download_button(
#                                 label=f"Descargar {out_name}",
#                                 data=xlsx_bio.getvalue(),
#                                 file_name=out_name,
#                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#                                 key=f"{key_prefix}_dl_xlsx",
#                             )
#                         except Exception as e:
#                             st.error(f"Error al procesar {up.name}: {e}")
#         if len(xlsx_buffers) > 1:
#             zip_bio = BytesIO()
#             with zipfile.ZipFile(zip_bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
#                 for fname, fb in xlsx_buffers:
#                     zf.writestr(fname, fb.getvalue())
#             zip_bio.seek(0)
#             st.download_button(
#                 "Descargar todos los archivos (.zip)",
#                 data=zip_bio.getvalue(),
#                 file_name="tcx_convertidos.zip",
#                 mime="application/zip",
#                 key="zip_all_dl",
#             )

# if __name__ == "__main__":
#     main()
