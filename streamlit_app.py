import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import TextIOWrapper, BytesIO, StringIO
import gzip, zipfile
from datetime import datetime

# Plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ====== Config ======
st.set_page_config(page_title="TCX_Pro → XLSX (EF & DA)", page_icon="📈", layout="centered")

# ====== Utilidades ======
NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
}

def parse_iso8601_z(ts: str):
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def get_text(elem, paths):
    for p in paths:
        node = elem.find(p, NS)
        if node is not None and node.text:
            return node.text.strip()
    return None

def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def to_int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None

def open_maybe_gzip_bytes(uploaded_file):
    """Devuelve un manejador de texto UTF-8 para .tcx o .tcx.gz subido."""
    name = uploaded_file.name.lower()
    if name.endswith(".gz"):
        gz = gzip.GzipFile(fileobj=BytesIO(uploaded_file.getvalue()), mode="rb")
        return TextIOWrapper(gz, encoding="utf-8")
    else:
        return TextIOWrapper(BytesIO(uploaded_file.getvalue()), encoding="utf-8")

def parse_tcx_to_rows(uploaded_file):
    f = open_maybe_gzip_bytes(uploaded_file)
    tree = ET.parse(f)
    root = tree.getroot()

    rows = []
    first_ts = None

    for act in root.findall(".//tcx:Activities/tcx:Activity", NS):
        sport = act.get("Sport")
        for li, lap in enumerate(act.findall("tcx:Lap", NS), start=1):
            for track in lap.findall("tcx:Track", NS):
                for ti, tp in enumerate(track.findall("tcx:Trackpoint", NS), start=1):
                    ts_txt = get_text(tp, ["tcx:Time"])
                    ts = parse_iso8601_z(ts_txt) if ts_txt else None
                    if ts and first_ts is None:
                        first_ts = ts
                    elapsed = (ts - first_ts).total_seconds() if (ts and first_ts) else None

                    lat = to_float(get_text(tp, ["tcx:Position/tcx:LatitudeDegrees"]))
                    lon = to_float(get_text(tp, ["tcx:Position/tcx:LongitudeDegrees"]))
                    alt = to_float(get_text(tp, ["tcx:AltitudeMeters"]))
                    dist = to_float(get_text(tp, ["tcx:DistanceMeters"]))
                    hr  = to_int(get_text(tp, ["tcx:HeartRateBpm/tcx:Value"]))
                    cad = to_int(get_text(tp, ["tcx:Cadence"]))

                    speed_mps = to_float(get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:Speed",
                        "tcx:Extensions/ns2:TPX/ns2:Speed",
                    ]))
                    watts = to_float(get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:Watts",
                        "tcx:Extensions/ns2:TPX/ns2:Watts",
                    ]))
                    run_spm = to_int(get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:RunCadence",
                        "tcx:Extensions/ns2:TPX/ns2:RunCadence",
                    ]))
                    if cad is None:
                        cad = to_int(get_text(tp, [
                            "tcx:Extensions/ns3:TPX/ns3:Cadence",
                            "tcx:Extensions/ns2:TPX/ns2:Cadence",
                        ]))

                    speed_kmh = speed_mps * 3.6 if speed_mps is not None else None

                    rows.append({
                        "activity_sport": sport,
                        "lap_index": li,
                        "trackpoint_index": ti,
                        "time_utc": ts.isoformat() if ts else None,
                        "elapsed_s": round(elapsed, 3) if elapsed is not None else None,
                        "latitude_deg": lat,
                        "longitude_deg": lon,
                        "altitude_m": alt,
                        "distance_m": dist,
                        "speed_mps": speed_mps,
                        "speed_kmh": round(speed_kmh, 3) if speed_kmh is not None else None,
                        "hr_bpm": hr,
                        "cadence_rpm": cad,
                        "run_cadence_spm": run_spm,
                        "power_w": watts,
                    })
    return rows

def rows_to_dataframe(rows) -> pd.DataFrame:
    from pandas import to_datetime

    if not rows:
        rows = [{
            "activity_sport": None, "lap_index": None, "trackpoint_index": None,
            "time_utc": None, "elapsed_s": None, "latitude_deg": None,
            "longitude_deg": None, "altitude_m": None, "distance_m": None,
            "speed_mps": None, "speed_kmh": None, "hr_bpm": None,
            "cadence_rpm": None, "run_cadence_spm": None, "power_w": None
        }]

    df = pd.DataFrame(rows)

    # Tipificar tiempo
    if "time_utc" in df.columns:
        dt = to_datetime(df["time_utc"], errors="coerce", utc=True).dt.tz_convert(None)
        df["time_utc"] = dt

    # Tipificar numéricos
    float_cols = ["elapsed_s","latitude_deg","longitude_deg","altitude_m",
                  "distance_m","speed_mps","speed_kmh","power_w"]
    int_cols   = ["hr_bpm","cadence_rpm","run_cadence_spm"]
    for c in float_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce", downcast="integer")

    # EF y DA
    if "power_w" in df.columns and "hr_bpm" in df.columns:
        df["ef_power_hr"] = df.apply(
            lambda r: (float(r["power_w"]) / float(r["hr_bpm"]))
                      if pd.notna(r["power_w"]) and pd.notna(r["hr_bpm"]) and float(r["hr_bpm"]) > 0
                      else float("nan"),
            axis=1
        )
        df["da"] = df["ef_power_hr"].diff()  # primer dato NaN

    # Orden por tiempo
    if "time_utc" in df.columns:
        df = df.sort_values("time_utc").reset_index(drop=True)

    return df

def rows_to_xlsx_bytes(rows, out_basename):
    """Crea un XLSX en memoria (BytesIO) con EF y DA, formateado."""
    from openpyxl.utils import get_column_letter

    df = rows_to_dataframe(rows)

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="TCX")
        ws = xw.book["TCX"]

        widths = {
            "activity_sport":14, "lap_index":10, "trackpoint_index":16,
            "time_utc":20, "elapsed_s":10, "latitude_deg":12, "longitude_deg":12,
            "altitude_m":11, "distance_m":12, "speed_mps":11, "speed_kmh":10,
            "hr_bpm":10, "cadence_rpm":12, "run_cadence_spm":16, "power_w":10,
            "ef_power_hr":12, "da":12
        }
        cols = list(df.columns)
        for i, col_name in enumerate(cols, start=1):
            ws.column_dimensions[get_column_letter(i)].width = widths.get(col_name, 12)

        def fmt(col_name, fmt_code):
            if col_name in cols:
                ci = cols.index(col_name) + 1
                for row in ws.iter_rows(min_row=2, min_col=ci, max_col=ci, max_row=ws.max_row):
                    for cell in row:
                        cell.number_format = fmt_code

        if "time_utc" in cols:
            fmt("time_utc", "yyyy-mm-dd hh:mm:ss")
        fmt("elapsed_s", "0.000")
        fmt("speed_kmh", "0.000")
        fmt("speed_mps", "0.000")
        fmt("distance_m", "0.00")
        fmt("altitude_m", "0.0")
        fmt("latitude_deg", "0.000000")
        fmt("longitude_deg", "0.000000")
        if "ef_power_hr" in cols:
            fmt("ef_power_hr", "0.000")
        if "da" in cols:
            fmt("da", "0.000")

    bio.seek(0)
    return bio, df

# ====== Gráficas ======
def make_plot_dual_panel(
    df: pd.DataFrame,
    title: str = "Análisis de Carga Fisiológica – Made4Try",
    y1_range=None,           # Potencia (panel superior, eje izq)
    y1_right_range=None,     # FC/Pendiente (panel superior, eje der)
    y2_range=None            # EF/DA (panel inferior)
) -> go.Figure:
    t  = df["elapsed_s"]
    p  = df.get("power_w")
    hr = df.get("hr_bpm")

    ef = df.get("ef_power_hr")
    if ef is None:
        ef = (df["power_w"] / df["hr_bpm"].replace({0: pd.NA}))
    da = df.get("da")
    if da is None:
        da = ef.diff()

    # Pendiente FC (bpm/s)
    dt = pd.Series(t).diff().replace(0, pd.NA).fillna(1)
    fc_slope = pd.Series(hr).diff().fillna(0) / dt

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        row_heights=[0.68, 0.32],
        specs=[[{"secondary_y": True}], [{}]]
    )

    # Panel superior
    fig.add_trace(go.Scatter(x=t, y=p,  name="Potencia (W)", mode="lines"),
                  row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=hr, name="FC (bpm)", mode="lines"),
                  row=1, col=1, secondary_y=True)
    fig.add_trace(go.Scatter(x=t, y=fc_slope, name="Pendiente FC (bpm/s)", mode="lines"),
                  row=1, col=1, secondary_y=True)

    # Panel inferior
    fig.add_trace(go.Scatter(x=t, y=ef, name="EF", mode="lines"),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=da, name="DA (ΔEF)", mode="lines",
                             line=dict(dash="dot")),
                  row=2, col=1)

    # Títulos
    fig.update_xaxes(title_text="Tiempo transcurrido (s)", row=2, col=1)
    fig.update_yaxes(title_text="Potencia (W)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="FC / Pendiente FC", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="EF / DA", row=2, col=1)

    # Rangos opcionales
    if y1_range:
        fig.update_yaxes(range=list(y1_range), row=1, col=1, secondary_y=False)
    if y1_right_range:
        fig.update_yaxes(range=list(y1_right_range), row=1, col=1, secondary_y=True)
    if y2_range:
        fig.update_yaxes(range=list(y2_range), row=2, col=1)

    fig.update_layout(
        title=title,
        legend=dict(orientation="h", x=0, y=1.12),
        template="plotly_white",
        margin=dict(l=50, r=50, t=70, b=50),
    )
    return fig

def make_plot_three_axes(
    df: pd.DataFrame,
    title: str = "Análisis de Carga Fisiológica – Made4Try",
    y_left_range=None,      # Potencia
    y_right_range=None,     # FC/Pendiente
    y_tertiary_range=None   # EF/DA
) -> go.Figure:
    t  = df["elapsed_s"]
    p  = df.get("power_w")
    hr = df.get("hr_bpm")

    ef = df.get("ef_power_hr")
    if ef is None:
        ef = (df["power_w"] / df["hr_bpm"].replace({0: pd.NA}))
    da = df.get("da")
    if da is None:
        da = ef.diff()

    # Pendiente FC (bpm/s)
    dt = pd.Series(t).diff().replace(0, pd.NA).fillna(1)
    fc_slope = pd.Series(hr).diff().fillna(0) / dt

    fig = go.Figure()

    # Y1 (izquierda): Potencia
    fig.add_trace(go.Scatter(x=t, y=p,  name="Potencia (W)", mode="lines", yaxis="y"))

    # Y2 (derecha): FC y pendiente
    fig.add_trace(go.Scatter(x=t, y=hr,       name="FC (bpm)",             mode="lines", yaxis="y2"))
    fig.add_trace(go.Scatter(x=t, y=fc_slope, name="Pendiente FC (bpm/s)", mode="lines", yaxis="y2"))

    # Y3 (derecha, ligeramente hacia adentro): EF y DA
    fig.add_trace(go.Scatter(x=t, y=ef, name="EF",       mode="lines", yaxis="y3"))
    fig.add_trace(go.Scatter(x=t, y=da, name="DA (ΔEF)", mode="lines", yaxis="y3",
                             line=dict(dash="dot")))

    layout = dict(
        title=title,
        xaxis=dict(title="Tiempo transcurrido (s)"),
        yaxis=dict(title="Potencia (W)"),  # izquierda
        yaxis2=dict(
            title="FC / Pendiente FC",
            overlaying="y",
            side="right",
            position=1.0
        ),
        yaxis3=dict(
            title="EF / DA",
            overlaying="y",
            side="right",
            position=0.98,  # separa rótulos de y2
            showgrid=False
        ),
        legend=dict(orientation="h", x=0, y=1.12),
        template="plotly_white",
        margin=dict(l=50, r=70, t=70, b=50),
    )

    # Rangos opcionales
    if y_left_range:
        layout["yaxis"]["range"] = list(y_left_range)
    if y_right_range:
        layout["yaxis2"]["range"] = list(y_right_range)
    if y_tertiary_range:
        layout["yaxis3"]["range"] = list(y_tertiary_range)

    fig.update_layout(**layout)
    return fig

# ====== UI ======
st.title("📈 TCX → XLSX (EF & DA)")
st.write("Arrastra uno o varios archivos **.tcx** o **.tcx.gz**. Obtendrás un **.xlsx** por sesión, con columnas **EF** y **DA** y una **gráfica HTML** interactiva.")

# Selector de modo de visualización (default: dos paneles)
chart_mode = st.radio(
    "Modo de visualización",
    options=["Dos paneles alineados (default)", "Eje terciario (1 panel)"],
    index=0,
    help="Los dos paneles mejoran la lectura de EF/DA; el eje terciario compacta todo en un solo panel."
)

# Ajustes manuales de ejes
with st.expander("Ajustes manuales de ejes (opcional)"):
    enable_ranges = st.checkbox("Definir rangos manuales")

    y1_min = y1_max = y1r_min = y1r_max = y2_min = y2_max = None
    yL_min = yL_max = yR_min = yR_max = yT_min = yT_max = None

    if enable_ranges:
        if chart_mode.startswith("Dos paneles"):
            st.caption("Panel superior")
            c1, c2, c3, c4 = st.columns(4)
            y1_min = c1.number_input("Potencia min", value=float(0), step=10.0)
            y1_max = c2.number_input("Potencia max", value=float(500), step=10.0)
            y1r_min = c3.number_input("FC/Pendiente min", value=float(0), step=5.0)
            y1r_max = c4.number_input("FC/Pendiente max", value=float(180), step=5.0)

            st.caption("Panel inferior")
            c5, c6 = st.columns(2)
            y2_min = c5.number_input("EF/DA min", value=float(-0.5), step=0.1, format="%.3f")
            y2_max = c6.number_input("EF/DA max", value=float(2.0), step=0.1, format="%.3f")
        else:
            st.caption("Eje izquierdo (Potencia)")
            c1, c2 = st.columns(2)
            yL_min = c1.number_input("Potencia min", value=float(0), step=10.0)
            yL_max = c2.number_input("Potencia max", value=float(500), step=10.0)

            st.caption("Eje derecho (FC / Pendiente)")
            c3, c4 = st.columns(2)
            yR_min = c3.number_input("FC/Pendiente min", value=float(0), step=5.0)
            yR_max = c4.number_input("FC/Pendiente max", value=float(180), step=5.0)

            st.caption("Tercer eje (EF / DA)")
            c5, c6 = st.columns(2)
            yT_min = c5.number_input("EF/DA min", value=float(-0.5), step=0.1, format="%.3f")
            yT_max = c6.number_input("EF/DA max", value=float(2.0), step=0.1, format="%.3f")

uploads = st.file_uploader(
    "Sube tus archivos (puedes seleccionar varios)",
    type=["tcx", "gz"],
    accept_multiple_files=True
)

def render_plot_and_download(df: pd.DataFrame, base_name: str):
    # Construir figura según modo y rangos
    if chart_mode.startswith("Dos paneles"):
        y1_range = (y1_min, y1_max) if (enable_ranges and y1_min is not None and y1_max is not None) else None
        y1r_range = (y1r_min, y1r_max) if (enable_ranges and y1r_min is not None and y1r_max is not None) else None
        y2_range = (y2_min, y2_max) if (enable_ranges and y2_min is not None and y2_max is not None) else None

        fig = make_plot_dual_panel(
            df,
            y1_range=y1_range,
            y1_right_range=y1r_range,
            y2_range=y2_range
        )
    else:
        yL_range = (yL_min, yL_max) if (enable_ranges and yL_min is not None and yL_max is not None) else None
        yR_range = (yR_min, yR_max) if (enable_ranges and yR_min is not None and yR_max is not None) else None
        yT_range = (yT_min, yT_max) if (enable_ranges and yT_min is not None and yT_max is not None) else None

        fig = make_plot_three_axes(
            df,
            y_left_range=yL_range,
            y_right_range=yR_range,
            y_tertiary_range=yT_range
        )

    st.plotly_chart(fig, use_container_width=True)

    html_buf = StringIO()
    fig.write_html(html_buf, include_plotlyjs="cdn", full_html=True)
    html_bytes = html_buf.getvalue().encode("utf-8")

    file_html = f"{base_name}_analisis.html"
    st.download_button(
        label="⬇️ Descargar gráfica HTML",
        data=html_bytes,
        file_name=file_html,
        mime="text/html",
        key=f"html_{file_html}"
    )
    st.info("Gráfica HTML interactiva con zoom/hover y ejes sincronizados.")

if uploads:
    xlsx_buffers = []
    for up in uploads:
        with st.spinner(f"Procesando {up.name}..."):
            try:
                rows = parse_tcx_to_rows(up)
                base = up.name
                if base.lower().endswith(".gz"):
                    base = base[:-3]
                if base.lower().endswith(".tcx"):
                    base = base[:-4]
                out_name = f"{base}.xlsx"

                bio, df = rows_to_xlsx_bytes(rows, base)
                xlsx_buffers.append((out_name, bio))

                st.success(f"✔ {out_name} listo")
                st.download_button(
                    label=f"⬇️ Descargar {out_name}",
                    data=bio.getvalue(),
                    file_name=out_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{out_name}"
                )

                # Gráfica para cada archivo procesado
                render_plot_and_download(df, base_name=base)

            except Exception as e:
                st.error(f"Error en {up.name}: {e}")

    # Botón para descargar TODO en un ZIP
    if len(xlsx_buffers) > 1:
        zip_bio = BytesIO()
        with zipfile.ZipFile(zip_bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname, fb in xlsx_buffers:
                zf.writestr(fname, fb.getvalue())
        zip_bio.seek(0)
        st.download_button(
            "⬇️ Descargar todos (.zip)",
            data=zip_bio.getvalue(),
            file_name="tcx_convertidos.zip",
            mime="application/zip"
        )
