# Exportar a XLSX y embeber HTML
# made4try/export_xlsx.py

from io import BytesIO
import pandas as pd
import numpy as np
from .config import DEFAULT_SHEET_NAME


def _sanitize_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Excel (openpyxl) no soporta bien:
      - pd.NA (pandas NA scalar)
      - NaN
      - inf / -inf
      - objetos complejos (dict/list/set/tuple)
    Este saneamiento evita errores tipo:
      "Cannot convert <NA> to Excel"
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    # Reemplaza inf/-inf por NaN
    out = out.replace([np.inf, -np.inf], np.nan)

    # Convierte columnas object con estructuras raras a string
    for c in out.columns:
        if out[c].dtype == "object":
            def _fix_obj(x):
                # pd.NA, NaN -> None
                if x is pd.NA:
                    return None
                if isinstance(x, float) and np.isnan(x):
                    return None
                # dict/list/tuple/set -> str
                if isinstance(x, (dict, list, tuple, set)):
                    return str(x)
                return x
            out[c] = out[c].map(_fix_obj)

    # Finalmente NaN/NA -> None (para todo el DF)
    out = out.where(pd.notna(out), None)

    return out


def dataframe_to_xlsx_bytes(
    df: pd.DataFrame,
    html_chart: str = None,
    sheet_name: str = DEFAULT_SHEET_NAME
) -> BytesIO:
    bio = BytesIO()

    df_x = _sanitize_for_excel(df)

    with pd.ExcelWriter(bio, engine="openpyxl") as xw:
        df_x.to_excel(xw, index=False, sheet_name=sheet_name)
        ws = xw.book[sheet_name]

        from openpyxl.utils import get_column_letter

        widths = {
            "fecha": 18, "documento": 20, "elapsed_s": 12,
            "power_w": 12, "hr_bpm": 12, "speed_kmh": 12, "dt_s": 12,
        }

        metrics = {
            "pct_ftp", "pct_fc_rel", "EFR", "IF", "ICR",
            "TSS_inc", "FSS_inc", "TSS_inc_ma30", "FSS_inc_ma30",
            "power_ma30", "hr_ma30",
            "TSS", "FSS", "TSS_total", "FSS_total",
            # Si ya existen en tu DF (no pasa nada si no):
            "EF_win", "DA_win_pct", "WIN_start_s", "WIN_end_s", "WIN_mins", "WIN_mode", "WIN_signal", "WIN_reason",
        }

        for i, col in enumerate(df_x.columns, start=1):
            w = widths.get(col, 14 if col in metrics else 12)
            ws.column_dimensions[get_column_letter(i)].width = w

        if html_chart:
            chart_sheet = xw.book.create_sheet("Gráficas")
            chart_sheet["A1"] = "Gráfica Interactiva de Carga"
            chart_sheet["A3"] = "Descarga el archivo HTML adjunto para ver la gráfica."
            preview = (html_chart[:500] + "...") if len(html_chart) > 500 else html_chart
            chart_sheet["A5"] = "Vista previa (HTML):"
            chart_sheet["A6"] = preview
            chart_sheet.column_dimensions["A"].width = 100

    bio.seek(0)
    return bio
