# Exportar a XLSX y embeber HTML
# export_xlsx.py
from io import BytesIO
import pandas as pd
import numpy as np
from .config import DEFAULT_SHEET_NAME


def _excel_safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Excel/openpyxl no soporta pd.NA. Convertimos:
      - pd.NA -> None
      - NaN/inf -> None (Excel tampoco ama inf)
    Mantiene strings/nums normales.
    """
    out = df.copy()

    # Reemplaza infs por NaN primero
    out = out.replace([np.inf, -np.inf], np.nan)

    # Convierte a object para permitir None
    out = out.astype("object")

    # Reemplaza pd.NA y NaN por None
    out = out.where(pd.notna(out), None)
    return out


def dataframe_to_xlsx_bytes(
    df: pd.DataFrame,
    html_chart: str = None,
    sheet_name: str = DEFAULT_SHEET_NAME
) -> BytesIO:
    bio = BytesIO()

    # 🔥 clave: dataframe saneado para Excel
    df_x = _excel_safe_df(df)

    with pd.ExcelWriter(bio, engine="openpyxl") as xw:
        df_x.to_excel(xw, index=False, sheet_name=sheet_name)
        ws = xw.book[sheet_name]

        from openpyxl.utils import get_column_letter

        widths = {
            "fecha": 18, "documento": 20, "elapsed_s": 12, "power_w": 12,
            "hr_bpm": 12, "speed_kmh": 12, "dt_s": 12,
        }

        metrics = {
            "pct_ftp", "pct_fc_rel", "EFR", "IF", "ICR",
            "TSS_inc", "FSS_inc", "TSS_inc_ma30", "FSS_inc_ma30",
            "power_ma30", "hr_ma30", "TSS", "FSS", "TSS_total", "FSS_total"
        }

        # Nuevas cols ventana (si existen)
        window_cols = {
            "WIN_mode", "WIN_mins", "WIN_signal", "WIN_start_s", "WIN_end_s",
            "WIN_score", "WIN_cv_intensity", "WIN_hr_cov", "WIN_reason",
            "EF_win", "DA_win_pct", "EF_half1", "EF_half2",
        }

        for i, col in enumerate(df_x.columns, start=1):
            if col in widths:
                w = widths[col]
            elif col in window_cols:
                w = 16 if col.startswith("WIN_") else 14
            else:
                w = 14 if col in metrics else 12
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
