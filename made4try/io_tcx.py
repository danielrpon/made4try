# Carga/parseo TCX/TCX.GZ → rows/DataFrame
# io_tcx.py
import xml.etree.ElementTree as ET
import pandas as pd
from .config import NS
from .utils import parse_iso8601_z, to_float, to_int, open_maybe_gzip_bytes

def _get_text(elem, paths):
    for p in paths:
        node = elem.find(p, NS)
        if node is not None and node.text:
            return node.text.strip()
    return None

def parse_tcx_to_rows(uploaded_file):
    f = open_maybe_gzip_bytes(uploaded_file)
    root = ET.parse(f).getroot()

    rows, first_ts = [], None
    for act in root.findall(".//tcx:Activities/tcx:Activity", NS):
        sport = act.get("Sport")
        for li, lap in enumerate(act.findall("tcx:Lap", NS), start=1):
            for track in lap.findall("tcx:Track", NS):
                for ti, tp in enumerate(track.findall("tcx:Trackpoint", NS), start=1):
                    ts_txt = _get_text(tp, ["tcx:Time"])
                    ts = parse_iso8601_z(ts_txt) if ts_txt else None
                    if ts and first_ts is None: first_ts = ts
                    elapsed = (ts-first_ts).total_seconds() if (ts and first_ts) else None

                    lat = to_float(_get_text(tp, ["tcx:Position/tcx:LatitudeDegrees"]))
                    lon = to_float(_get_text(tp, ["tcx:Position/tcx:LongitudeDegrees"]))
                    alt = to_float(_get_text(tp, ["tcx:AltitudeMeters"]))
                    dist = to_float(_get_text(tp, ["tcx:DistanceMeters"]))
                    hr   = to_int(_get_text(tp, ["tcx:HeartRateBpm/tcx:Value"]))
                    cad  = to_int(_get_text(tp, ["tcx:Cadence"]))

                    speed_mps = to_float(_get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:Speed",
                        "tcx:Extensions/ns2:TPX/ns2:Speed"]))
                    watts = to_float(_get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:Watts",
                        "tcx:Extensions/ns2:TPX/ns2:Watts"]))
                    run_spm = to_int(_get_text(tp, [
                        "tcx:Extensions/ns3:TPX/ns3:RunCadence",
                        "tcx:Extensions/ns2:TPX/ns2:RunCadence"]))

                    if cad is None:
                        cad = to_int(_get_text(tp, [
                            "tcx:Extensions/ns3:TPX/ns3:Cadence",
                            "tcx:Extensions/ns2:TPX/ns2:Cadence"]))

                    speed_kmh = speed_mps * 3.6 if speed_mps is not None else None

                    rows.append({
                        "activity_sport": sport,
                        "lap_index": li,
                        "trackpoint_index": ti,
                        "time_utc": ts.isoformat() if ts else None,
                        "elapsed_s": round(elapsed,3) if elapsed is not None else None,
                        "latitude_deg": lat, "longitude_deg": lon, "altitude_m": alt,
                        "distance_m": dist, "speed_mps": speed_mps, "speed_kmh": speed_kmh,
                        "hr_bpm": hr, "cadence_rpm": cad, "run_cadence_spm": run_spm,
                        "power_w": watts
                    })
    return rows

def rows_to_dataframe(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame([{
            "activity_sport": None, "lap_index": None, "trackpoint_index": None,
            "time_utc": None, "elapsed_s": None, "latitude_deg": None,
            "longitude_deg": None, "altitude_m": None, "distance_m": None,
            "speed_mps": None, "speed_kmh": None, "hr_bpm": None,
            "cadence_rpm": None, "run_cadence_spm": None, "power_w": None
        }])

    df = pd.DataFrame(rows)
    # Tipados
    num_float = ["elapsed_s","latitude_deg","longitude_deg","altitude_m",
                 "distance_m","speed_mps","speed_kmh","power_w"]
    num_int = ["hr_bpm","cadence_rpm","run_cadence_spm"]
    for c in num_float: 
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in num_int:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce", downcast="integer")
    return df