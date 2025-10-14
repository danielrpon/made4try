# =========================
# made4try/config.py
# =========================

# --------- UI ----------
PAGE_TITLE = "TCX → XLSX (EFR/IF/ICR/TSS/FSS)"
PAGE_ICON  = "📈"
LAYOUT     = "centered"   # cambia a "wide" si prefieres más espacio

# --------- Ventanas y defaults ----------
# Ventana (en segundos) para promedios móviles de curvas de carga (TSS/FSS) mostradas.
ROLLING_WINDOW_SECONDS   = 30

# NUEVO: suavizado de potencia y FC para visualización (no afecta TSS/FSS).
# Recomendado: 5s si muestreos ~1 Hz; 10s si hay más ruido/intervalos irregulares.
DISPLAY_SMOOTH_SECONDS   = 5

# Opcional: ventana para reemplazar FC inválida (NaN/<=0) al calcular FSS (sí afecta FSS).
# Útil cuando hay huecos largos en la FC; 20–30s suele ser estable.
HR_FILL_MA_SECONDS       = 30

# Nombre por defecto de la hoja en Excel
DEFAULT_SHEET_NAME = "DATA"

# --------- Namespaces TCX ----------
NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
}
