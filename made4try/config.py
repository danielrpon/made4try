# =========================
# made4try/config.py
# =========================

# --------- UI ----------
PAGE_TITLE = "TCX → XLSX (EFR/IF/ICR/TSS/FSS)"
PAGE_ICON  = "📈"
LAYOUT     = "centered"  # usa "wide" si prefieres más espacio horizontal

# --------- Ventanas y defaults ----------
# MA para visualizar incrementos de carga (ΔTSS/ΔFSS) en los gráficos
ROLLING_WINDOW_SECONDS = 30

# Suavizado visual de Potencia/FC (no afecta TSS/FSS). Lo puede sobreescribir el slider.
DISPLAY_SMOOTH_SECONDS = 5

# Ventana para rellenar FC inválida (NaN/<=0) al calcular FSS (sí afecta FSS)
HR_FILL_MA_SECONDS = 30

# Nombre de la hoja en Excel
DEFAULT_SHEET_NAME = "DATA"

# --------- Namespaces TCX ----------
NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
}
