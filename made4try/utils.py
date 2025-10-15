# =========================
# made4try/utils.py
# =========================
from __future__ import annotations

import os
import re
from typing import Optional, Any, Iterable

import pandas as pd


def clean_base_name(name: str) -> str:
    """
    Devuelve un nombre base sin extensiones .tcx ni .gz (case-insensitive).
    Ejemplos:
        'actividad.TCX'      -> 'actividad'
        'myfile.tcx.gz'      -> 'myfile'
        'ruta/act.tcx'       -> 'act'
        'act'                -> 'act'
    """
    if not name:
        return "archivo"
    base = os.path.basename(name)
    # quita .gz si está al final
    if base.lower().endswith(".gz"):
        base = base[:-3]
    # quita .tcx si está al final
    if base.lower().endswith(".tcx"):
        base = base[:-4]
    # limpia espacios sobrantes
    return base.strip() or "archivo"


def safe_div(a: float | int | None, b: float | int | None, default: Optional[float] = None) -> Optional[float]:
    """
    División segura que evita ZeroDivisionError y None.
    - Devuelve `default` si 'b' es 0/None o si 'a' es None.
    """
    try:
        if a is None or b in (None, 0, 0.0):
            return default
        return float(a) / float(b)
    except Exception:
        return default


def coerce_numeric(s: Iterable[Any]) -> pd.Series:
    """
    Convierte un iterable a Serie numérica (float) con NaN donde no se pueda.
    """
    return pd.to_numeric(pd.Series(s), errors="coerce")


def ensure_sorted_by(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Ordena un DataFrame por las columnas dadas si existen y hay valores.
    No modifica el original.
    """
    df2 = df.copy()
    valid = [c for c in cols if c in df2.columns and df2[c].notna().any()]
    if valid:
        df2 = df2.sort_values(valid).reset_index(drop=True)
    return df2
