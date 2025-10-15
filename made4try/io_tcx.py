# =========================
# made4try/io_tcx.py
# =========================
from __future__ import annotations

import gzip
from io import BytesIO, TextIOWrapper
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Iterable, List, Dict, Any, Optional

import pandas as pd

from .config import NS


# ---------- Utilidades de parseo ----------

def _parse_iso8601_z(ts: Optional[str]) -> Optional[datetime]:
    """
    Parsea timestamps ISO 8601, aceptando sufijo 'Z' (UTC).
    Devuelve naive datetime (sin tz) para facilitar cálculos posteriores.
    """
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(ts)
        # Devuelve naive en hora local del objeto (si trae tz, la eliminamos)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        return None


def _get_text(elem: ET.Element, paths: Iterable[str]) -> Optional[str]:
    """
    Extrae el .text de la primera ruta XPath que exista en 'elem' usando NS.
    """
    for p in paths:
        node = elem.find(p, NS)
        if node is not None and node.text:
            return node.text.strip()
    return None


def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        return int(float(x)) if x is not None else None
    except (TypeError, ValueError):
        return None


def _open_maybe_gzip_bytes(uploaded_file) -> TextIOWrapper:
    """
    Devuelve un manejador de texto UTF-8 para un archivo subido .tcx o .tcx.gz.
    'uploaded_file' debe exponer .name y .getvalue() (como los de Streamlit).
    """
    name = (uploaded_file.name or "").lower()
    raw = uploaded_file.getvalue()
    if name.endswith(".gz"):
        gz = gzip.GzipFile(fileobj=BytesIO(raw), mode="rb")
        return TextIOWrapper(gz, encoding="utf-8")
    return TextIOWrapper(BytesIO(raw), encoding="utf-8")


# ---------- Parseo a filas (dicts) ----------

def parse_tcx_to_rows(uploaded_file) -> List[Dict[str, Any]]:
    """
    Parsea un archivo TCX y devuelve una lista de dicts (uno por Trackpoint).
    Campos estándar + extensiones comunes de Garmin (ns2/ns3).
    """
    f = _open_maybe_gzip_bytes(uploaded_file)
    tree = ET.parse(f)
    root = tree.getroot()

    rows: List[Dict[str, Any]] = []
    first_ts: Optional[datetime] = None

    # Actividades → Laps → Tracks → Trackpoints
    for act in root.findall(".//tcx:Activities/tcx:Activity", NS):
        sport = act.get("Sport")
        for li, lap in enumerate(act.findall("tcx:Lap", NS), start=1):
            for track in lap.findall("tcx:Track", NS):
                for ti, tp in enumerate(track.findall("tcx:Trackpoint", NS), start=1):
                    # Tiempo
                    ts_txt = _get_text(tp, ["tcx:Time"])
                    ts = _parse_iso8601_z(ts_txt) if ts_txt else None
                    if ts and first_ts is None:
                        first_ts = ts
                    elapsed = (ts - first_ts).total_seconds() if (ts and first_ts) else None

                    # Posición / métricas básicas
                    lat = _to_float(_get_text(tp, ["tcx:Position/tcx:LatitudeDegrees"]))
                    lon = _to_float(_get_text(tp, ["tcx:Position/tcx:LongitudeDegrees"]))
                    alt = _to_float(_get_text(tp, ["tcx:AltitudeMeters"]))
                    dist = _to_float(_get_text(tp, ["tcx:DistanceMeters"]))
                    hr   = _to_int(_get_text(tp, ["tcx:HeartRateBpm/tcx:Value"]))
                    cad  = _to_int(_get_text(tp, ["tcx:Cadence"]))

                    # Extensiones comunes (ns3 primero, luego ns2 por compatibilidad)
                    speed_mps = _to_float(_get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:Speed",
                        "tcx:Extensions/ns2:TPX/ns2:Speed",
                    ]))
                    watts = _to_float(_get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:Watts",
                        "tcx:Extensions/ns2:TPX/ns2:Watts",
                    ]))
                    run_spm = _to_int(_get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:RunCadence",
                        "tcx:Extensions/ns2:TPX/ns2:RunCadence",
                    ]))
                    if cad is None:
                        cad = _to_int(_get_text(tp, [
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


# ---------- Conversión a DataFrame ----------

def rows_to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convierte la lista de dicts en un DataFrame tipado y ordenado por tiempo.
    Asegura tipos numéricos y datetime coherentes para pasos posteriores.
    """
    from pandas import to_datetime

    # Si no hay filas, devolvemos una estructura mínima vacía tipada
    if not rows:
        rows = [{
            "activity_sport": None,
            "lap_index": None,
            "trackpoint_index": None,
            "time_utc": None,
            "elapsed_s": None,
            "latitude_deg": None,
            "longitude_deg": None,
            "altitude_m": None,
            "distance_m": None,
            "speed_mps": None,
            "speed_kmh": None,
            "hr_bpm": None,
            "cadence_rpm": None,
            "run_cadence_spm": None,
            "power_w": None,
        }]

    df = pd.DataFrame(rows)

    # Tipificar fechas (convertimos a naive datetime)
    if "time_utc" in df.columns:
        dt = to_datetime(df["time_utc"], errors="coerce", utc=True).dt.tz_convert(None)
        df["time_utc"] = dt

    # Tipificar numéricos
    float_cols = [
        "elapsed_s", "latitude_deg", "longitude_deg", "altitude_m",
        "distance_m", "speed_mps", "speed_kmh", "power_w"
    ]
    int_cols = ["hr_bpm", "cadence_rpm", "run_cadence_spm"]

    for c in float_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce", downcast="integer")

    # Ordenar por tiempo si existe; si no, por elapsed_s
    if "time_utc" in df.columns and df["time_utc"].notna().any():
        df = df.sort_values("time_utc").reset_index(drop=True)
    elif "elapsed_s" in df.columns and df["elapsed_s"].notna().any():
        df = df.sort_values("elapsed_s").reset_index(drop=True)

    return df
