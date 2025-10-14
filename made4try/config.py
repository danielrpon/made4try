# Constantes y parámetros (ej. ventana MA, nombres)
# config.py
PAGE_TITLE = "TCX → XLSX (EFR/IF/ICR/TSS/FSS)"
PAGE_ICON = "📈"
LAYOUT = "centered"

# Ventanas y defaults
ROLLING_WINDOW_SECONDS = 30
# HR_FILL_MA_SECONDS     = 10   # para reemplazo de FC al calcular FSS
DEFAULT_SHEET_NAME = "DATA"

# Namespaces TCX
NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
}
