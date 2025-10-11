# -*- coding: utf-8 -*-
# =======================
#  TCX → XLSX (EFR / IF / ICR / TSS / FSS)
#  Correcciones incluidas:
#   - Solicita FTP y FC_20min_max (mejores 20' últimos 90 días) por archivo.
#   - Mantiene solo columnas mínimas: fecha, documento, elapsed_s, power_w, hr_bpm, speed_kmh.
#   - Calcula: %FTP, %FC_rel, EFR, IF, ICR_clásico (IF×EFR), ICR_alt (IF/EFR), TSS_seg, FSS_seg.
#   - Selector para usar ICR_clásico o ICR_alt al computar FSS/mostrar en gráfica.
# =======================

import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import TextIOWrapper, BytesIO, StringIO
import gzip, zipfile
from datetime import datetime

# Plotly
import plotly.graph_objects as go

# ====== Config ======
st.set_page_config(page_title="TCX → XLSX (EFR/IF/ICR/TSS/FSS)", page_icon="📈", layout="centered")

# ====== Utilidades ======
NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
}

def parse_iso8601_z(ts: str):
    try:
        if ts and ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts) if ts else None
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

    # Orden por tiempo
    if "time_utc" in df.columns:
        df = df.sort_values("time_utc").reset_index(drop=True)

    return df

def add_metrics_minimal(df: pd.DataFrame, base_name: str, ftp: float, fc20: float, icr_mode: str) -> pd.DataFrame:
    """
    Mantiene columnas mínimas y calcula métricas:
    - %FTP, %FC_rel, EFR, IF, ICR_clásico (IF×EFR), ICR_alt (IF/EFR), TSS_seg, FSS_seg.
    icr_mode: "clasico" usa ICR_clásico para FSS. "alternativo" usa ICR_alt para FSS.
    """
    df = df.copy()

    # Derivar fecha (de la primera muestra válida) y documento (nombre base)
    fecha = None
    if "time_utc" in df.columns and pd.api.types.is_datetime64_any_dtype(df["time_utc"]):
        if df["time_utc"].notna().any():
            fecha = df["time_utc"].dropna().iloc[0].date()

    df["fecha"] = fecha.isoformat() if fecha else None
    df["documento"] = base_name

    # Selección mínima
    keep = {
        "fecha": df.get("fecha"),
        "documento": df.get("documento"),
        "elapsed_s": pd.to_numeric(df.get("elapsed_s"), errors="coerce"),
        "power_w": pd.to_numeric(df.get("power_w"), errors="coerce"),
        "hr_bpm": pd.to_numeric(df.get("hr_bpm"), errors="coerce"),
        "speed_kmh": pd.to_numeric(df.get("speed_kmh"), errors="coerce"),
    }
    m = pd.DataFrame(keep)

    # Parámetros
    ftp = float(ftp)
    fc20 = float(fc20)

    # Evitar divisiones por cero
    power = m["power_w"].fillna(0.0)
    hr = m["hr_bpm"].astype(float).replace({0.0: pd.NA})

    # %FTP y %FC_rel
    pct_ftp = (power / ftp) * 100.0
    pct_fc  = (hr / fc20) * 100.0

    # EFR = %FTP / %FC_rel  = (P/FTP) / (HR/FC20)
    efr = pct_ftp / pct_fc

    # IF
    IF = power / ftp

    # ICRs
    icr_clasico = IF * efr        # recomendado por defecto
    icr_alt     = IF / efr        # variante solicitada (IF × 1/EFR)

    # TSS y FSS por segundo
    tss_seg = (IF ** 2) / (ftp * 36.0)
    if icr_mode == "alternativo":
        icr_for_fss = icr_alt
    else:
        icr_for_fss = icr_clasico
    fss_seg = (icr_for_fss ** 2) / (ftp * 36.0)

    # Asignar al DF
    m["pct_ftp"]    = pct_ftp
    m["pct_fc_rel"] = pct_fc
    m["EFR"]        = efr
    m["IF"]         = IF
    m["ICR"]        = icr_clasico
    m["ICR_alt"]    = icr_alt
    m["TSS_seg"]    = tss_seg
    m["FSS_seg"]    = fss_seg

    return m

def dataframe_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "DATA") -> BytesIO:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name=sheet_name)
        ws = xw.book[sheet_name]

        # Ajuste de anchos simple
        from openpyxl.utils import get_column_letter
        for i, col in enumerate(df.columns, start=1):
            width = 12
            if col in ("fecha", "documento"): width = 18
            if col in ("elapsed_s", "power_w", "hr_bpm", "speed_kmh"): width = 12
            if col in ("pct_ftp","pct_fc_rel","EFR","IF","ICR","ICR_alt","TSS_seg","FSS_seg"): width = 12
            ws.column_dimensions[get_column_letter(i)].width = width
    bio.seek(0)
    return bio

# ====== Gráfica carga (TSS vs FSS) + señales base ======
def make_plot_loads(df: pd.DataFrame, title: str, show_base: bool = True) -> go.Figure:
    t = df["elapsed_s"]
    fig = go.Figure()

    # Líneas principales de carga
    fig.add_trace(go.Scatter(x=t, y=df["TSS_seg"], name="TSS (seg)", mode="lines"))
    fig.add_trace(go.Scatter(x=t, y=df["FSS_seg"], name="FSS (seg)", mode="lines"))

    # Señales base opcionales
    if show_base:
        if "power_w" in df.columns:
            fig.add_trace(go.Scatter(x=t, y=df["power_w"], name="Potencia (W)", mode="lines", yaxis="y2"))
        if "hr_bpm" in df.columns:
            fig.add_trace(go.Scatter(x=t, y=df["hr_bpm"], name="FC (bpm)", mode="lines", yaxis="y3"))

    # Layout con múltiples ejes
    layout = dict(
        title=title,
        xaxis=dict(title="Tiempo (s)"),
        yaxis=dict(title="Carga por segundo", rangemode="tozero"),      # TSS/FSS
        yaxis2=dict(title="Potencia (W)", overlaying="y", side="right", position=1.0, showgrid=False),
        yaxis3=dict(title="FC (bpm)", overlaying="y", side="right", position=0.98, showgrid=False),
        legend=dict(orientation="h", x=0, y=1.12),
        template="plotly_white",
        margin=dict(l=60, r=80, t=70, b=50),
    )
    fig.update_layout(**layout)
    return fig

# ====== UI ======
st.title("📈 TCX → XLSX con EFR / IF / ICR / TSS / FSS")
st.write("""
Sube uno o varios **.tcx** o **.tcx.gz**.
Por **cada archivo** deberás ingresar:
- **FTP (W)**
- **FC_20min_max (bpm)** → *promedio de tus mejores 20 minutos de los últimos 90 días*.
""")

# Selector global de ICR a utilizar para FSS/Gráfica
icr_mode = st.radio(
    "Modo de ICR a usar para **FSS** y visualización:",
    options=["ICR = IF × EFR (recomendado)", "ICR = IF ÷ EFR (alternativo)"],
    index=0,
    help="Puedes exportar ambos ICR en el Excel; este selector define cuál se usa para calcular FSS_seg y graficar."
)
icr_mode_key = "clasico" if icr_mode.startswith("ICR = IF ×") else "alternativo"

uploads = st.file_uploader(
    "Sube tus archivos (puedes seleccionar varios)",
    type=["tcx", "gz"],
    accept_multiple_files=True
)

def clean_base_name(name: str) -> str:
    base = name
    if base.lower().endswith(".gz"):
        base = base[:-3]
    if base.lower().endswith(".tcx"):
        base = base[:-4]
    return base

def render_plot_and_download(df: pd.DataFrame, base_name: str):
    fig = make_plot_loads(df, title=f"Dinámica de Carga – {base_name}", show_base=True)
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
    st.info("Gráfica HTML interactiva con zoom/hover.")

if uploads:
    xlsx_buffers = []  # [(filename, BytesIO)]

    for up in uploads:
        st.markdown("---")
        st.subheader(f"Parámetros para: `{up.name}`")
        c1, c2 = st.columns(2)
        ftp = c1.number_input(f"FTP (W) – {up.name}", min_value=1, step=1, key=f"ftp_{up.name}")
        fc20 = c2.number_input(f"FC_20min_max (bpm) – {up.name}", min_value=1, step=1, key=f"fc20_{up.name}")
        avanzar = st.button(f"Procesar {up.name}", key=f"proc_{up.name}")

        if avanzar:
            if not (ftp and fc20):
                st.warning("Ingresa FTP y FC_20min_max para continuar.")
            else:
                with st.spinner(f"Procesando {up.name}..."):
                    try:
                        # Parseo y DataFrame base
                        rows = parse_tcx_to_rows(up)
                        df_raw = rows_to_dataframe(rows)

                        # Cálculo de métricas y reducción a columnas mínimas
                        base = clean_base_name(up.name)
                        df_final = add_metrics_minimal(df_raw, base_name=base, ftp=ftp, fc20=fc20, icr_mode=icr_mode_key)

                        # Exportar a XLSX (con métricas)
                        out_name = f"{base}.xlsx"
                        xlsx_bio = dataframe_to_xlsx_bytes(df_final, sheet_name="DATA")
                        xlsx_buffers.append((out_name, xlsx_bio))

                        st.success(f"✔ {out_name} listo")
                        st.download_button(
                            label=f"⬇️ Descargar {out_name}",
                            data=xlsx_bio.getvalue(),
                            file_name=out_name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{out_name}"
                        )

                        # Gráfica y HTML
                        render_plot_and_download(df_final, base_name=base)

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
