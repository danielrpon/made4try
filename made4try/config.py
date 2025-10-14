# =========================
# made4try/config.py
# =========================

# --------- UI ----------
PAGE_TITLE = "TCX → XLSX (EFR/IF/ICR/TSS/FSS)"
PAGE_ICON  = "📈"
LAYOUT     = "centered"   # cambia a "wide" si prefieres más espacio

# --------- Ventanas y defaults ----------

# Ventana (en segundos) para promedios móviles de curvas de carga (TSS/FSS) mostradas.
ROLLING_WINDOW_SECONDS = 30

# Ventana para suavizado de potencia y FC (visualización)
# Recomendado: 5s si el muestreo es de ~1 Hz; 10s si los datos son más ruidosos o dispares.
DISPLAY_SMOOTH_SECONDS = 5

# Ventana para interpolar y reemplazar FC inválida (NaN/<=0) al calcular FSS.
# Este valor sí afecta el cálculo final de métricas de carga.
# Usualmente 20–30s da resultados estables si hay huecos largos en el registro de FC.
HR_FILL_MA_SECONDS = 30

# Nombre por defecto de la hoja de datos exportada a Excel
DEFAULT_SHEET_NAME = "DATA"

# --------- Namespaces TCX ----------
NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns2": "http://www.garmin.com/xmlschemas/ActivityExtension/v1",
}
