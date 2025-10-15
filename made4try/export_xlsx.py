# =========================
# made4try/export_xlsx.py
# =========================
from io import BytesIO
import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from .config import DEFAULT_SHEET_NAME

def _set_col_widths(ws, df: pd.DataFrame):
    """
    Ajusta los anchos de columna según tipo de dato/columna.
    """
    # Valores base
    default_w = 12
    wide_cols = {"fecha", "documento", "time_utc"}
    narrow_cols = set()

    # Columnas con números más anchos
    medium_cols = {
        "elapsed_s", "dt_s", "distance_m",
        "power_w", "power_smooth", "power_ma30",
        "hr_bpm", "hr_smooth", "hr_ma30",
        "speed_mps", "speed_kmh",
        "pct_ftp", "pct_fc_rel", "EFR", "IF", "ICR",
        "TSS_inc", "FSS_inc", "TSS_inc_ma30", "FSS_inc_ma30",
        "TSS", "FSS", "TSS_total", "FSS_total",
    }

    for idx, col in enumerate(df.columns, start=1):
        if col in wide_cols:
            width = 18
        elif col in medium_cols:
            width = 14
        elif col in narrow_cols:
            width = 10
        else:
            width = default_w
        ws.column_dimensions[get_column_letter(idx)].width = width

def _apply_table_style(ws, df: pd.DataFrame):
    """
    Congela fila de encabezado, activa autofiltro y alinea encabezados.
    """
    # Congelar encabezado
    ws.freeze_panes = "A2"

    # Autofiltro
    max_col = get_column_letter(ws.max_column)
    max_row = ws.max_row
    ws.auto_filter.ref = f"A1:{max_col}{max_row}"

    # Estilo encabezados
    header_font = Font(bold=True)
    header_alignment = Alignment(vertical="center")
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = header_alignment

def _apply_number_formats(ws, df: pd.DataFrame):
    """
    Formatos de número básicos para algunas columnas típicas.
    """
    # Mapas de formatos por nombre de columna
    pct_cols = {"pct_ftp", "pct_fc_rel"}  # porcentaje
    one_dec_cols = {"speed_kmh"}          # 1 decimal
    two_dec_cols = {"EFR", "IF", "ICR"}   # 2 decimales
    one_dec_load = {"TSS", "FSS", "TSS_total", "FSS_total"}
    four_dec_inc = {"TSS_inc", "FSS_inc", "TSS_inc_ma30", "FSS_inc_ma30"}

    name_to_idx = {name: idx for idx, name in enumerate(df.columns, start=1)}

    for col in pct_cols:
        if col in name_to_idx:
            col_idx = name_to_idx[col]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col_idx).number_format = "0.0%"

            # Si tus % vienen en 0–100, cambia a 0.0% dividiendo por 100 antes de exportar
            # o usa "0.0" como formato. Aquí asumimos 0–100, así que usamos 0.0
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col_idx).number_format = "0.0"

    for col in one_dec_cols:
        if col in name_to_idx:
            col_idx = name_to_idx[col]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col_idx).number_format = "0.0"

    for col in two_dec_cols:
        if col in name_to_idx:
            col_idx = name_to_idx[col]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col_idx).number_format = "0.00"

    for col in one_dec_load:
        if col in name_to_idx:
            col_idx = name_to_idx[col]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col_idx).number_format = "0.0"

    for col in four_dec_inc:
        if col in name_to_idx:
            col_idx = name_to_idx[col]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col_idx).number_format = "0.0000"

def dataframe_to_xlsx_bytes(
    df: pd.DataFrame,
    html_chart: str | None = None,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> BytesIO:
    """
    Exporta un DataFrame a un buffer XLSX en memoria, con:
      - hoja de datos (ancho de columnas + filtros + formatos)
      - hoja 'Gráficas' con preview de HTML (si se pasa html_chart)
    """
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as xw:
        # Hoja de datos
        df.to_excel(xw, index=False, sheet_name=sheet_name)
        ws = xw.book[sheet_name]

        _set_col_widths(ws, df)
        _apply_table_style(ws, df)
        _apply_number_formats(ws, df)

        # Hoja de gráficas (preview HTML)
        if html_chart:
            chart_sheet = xw.book.create_sheet("Gráficas")

            # Título
            chart_sheet["A1"] = "Gráfica Interactiva de Carga"
            chart_sheet["A1"].font = Font(bold=True, size=14)

            # Nota
            chart_sheet["A3"] = "Para ver la gráfica interactiva completa, usa el archivo HTML descargado."
            chart_sheet["A3"].font = Font(italic=True)

            # Vista previa (texto)
            chart_sheet["A5"] = "Vista previa (HTML):"
            preview = html_chart[:500] + ("..." if len(html_chart) > 500 else "")
            chart_sheet["A6"] = preview
            chart_sheet["A6"].alignment = Alignment(wrap_text=True)

            # Ajuste de ancho para lectura
            chart_sheet.column_dimensions["A"].width = 100
            chart_sheet.row_dimensions[6].height = 140

    bio.seek(0)
    return bio
