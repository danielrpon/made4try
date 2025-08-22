import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import TextIOWrapper, BytesIO
import gzip, zipfile
from datetime import datetime

# ====== Config ======
st.set_page_config(page_title="TCX → XLSX (EF & DA)", page_icon="📈", layout="centered")

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

def rows_to_xlsx_bytes(rows, out_basename):
    """Crea un XLSX en memoria (BytesIO) con EF y DA, formateado."""
    from pandas import to_datetime
    import pandas as pd
    from openpyxl.utils import get_column_letter

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
        df = df.sort_values("time_utc")

    # Escribir a BytesIO
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
    return bio

# ====== UI ======
st.title("📈 TCX → XLSX (EF & DA)")
st.write("Arrastra uno o varios archivos **.tcx** o **.tcx.gz**. Obtendrás un **.xlsx** limpio por cada sesión, con columnas **EF** y **DA**.")

uploads = st.file_uploader(
    "Sube tus archivos (puedes seleccionar varios)",
    type=["tcx", "gz"],
    accept_multiple_files=True
)

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

                bio = rows_to_xlsx_bytes(rows, base)
                xlsx_buffers.append((out_name, bio))

                st.success(f"✔ {out_name} listo")
                st.download_button(
                    label=f"⬇️ Descargar {out_name}",
                    data=bio.getvalue(),
                    file_name=out_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{out_name}"
                )
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