# =========================
# made4try/plots.py
# =========================
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import StringIO

def _pick(df, smooth_col: str, raw_col: str):
    """Devuelve la serie suavizada si existe; si no, la cruda. También retorna la etiqueta."""
    if smooth_col in df.columns and df[smooth_col].notna().any():
        return df[smooth_col], True
    return df.get(raw_col), False

def make_plot_loads(df, title: str, show_base: bool = True) -> go.Figure:
    """
    Gráfico principal con TSS/FSS acumulados y señales base opcionales.
    Si existen columnas 'power_smooth' y/o 'hr_smooth', las usa para la visualización.
    """
    t = df["elapsed_s"]
    fig = go.Figure()

    # TSS/FSS acumulados
    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines"))
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines"))

    # Señales base (visual)
    if show_base:
        p_series, p_is_smooth = _pick(df, "power_smooth", "power_w")
        h_series, h_is_smooth = _pick(df, "hr_smooth", "hr_bpm")

        if p_series is not None:
            fig.add_trace(
                go.Scatter(
                    x=t, y=p_series,
                    name="Potencia (suav.)" if p_is_smooth else "Potencia (W)",
                    mode="lines", yaxis="y2"
                )
            )
        if h_series is not None:
            fig.add_trace(
                go.Scatter(
                    x=t, y=h_series,
                    name="FC (suav.)" if h_is_smooth else "FC (bpm)",
                    mode="lines", yaxis="y3"
                )
            )

    fig.update_layout(
        title=title,
        xaxis=dict(title="Tiempo (s)"),
        yaxis=dict(title="Carga acumulada (TSS/FSS)", rangemode="tozero"),
        yaxis2=dict(title="Potencia (W)", overlaying="y", side="right",
                    position=1.0, showgrid=False),
        yaxis3=dict(title="FC (bpm)", overlaying="y", side="right",
                    position=0.98, showgrid=False),
        legend=dict(orientation="h", x=0, y=1.12),
        template="plotly_white",
        margin=dict(l=60, r=80, t=70, b=50),
    )
    return fig


def make_plot_loads_dual(df, title: str) -> go.Figure:
    """
    Dos subplots:
      (1) Carga acumulada + promedios móviles de 30s (TSS/FSS_inc_ma30) y señales suavizadas.
      (2) Dinámica instantánea ΔTSS/ΔFSS.
    """
    t = df["elapsed_s"]
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            "Carga Acumulada + Promedios (30s)",
            "Dinámica Instantánea (ΔTSS/ΔFSS)"
        ),
        vertical_spacing=0.12, row_heights=[0.6, 0.4]
    )

    # Curvas de carga (subplot 1)
    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines", yaxis="y1"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines", yaxis="y2"), row=1, col=1)
    if "TSS_inc_ma30" in df:
        fig.add_trace(go.Scatter(x=t, y=df["TSS_inc_ma30"], name="ΔTSS (MA30s)", mode="lines", yaxis="y3"), row=1, col=1)
    if "FSS_inc_ma30" in df:
        fig.add_trace(go.Scatter(x=t, y=df["FSS_inc_ma30"], name="ΔFSS (MA30s)", mode="lines", yaxis="y4"), row=1, col=1)

    # Señales suavizadas para contexto (si existen)
    p_series, p_is_smooth = _pick(df, "power_smooth", "power_w")
    h_series, h_is_smooth = _pick(df, "hr_smooth", "hr_bpm")
    if p_series is not None:
        fig.add_trace(
            go.Scatter(x=t, y=p_series,
                       name="Potencia (suav.)" if p_is_smooth else "Potencia (W)",
                       mode="lines", yaxis="y5"),
            row=1, col=1
        )
    if h_series is not None:
        fig.add_trace(
            go.Scatter(x=t, y=h_series,
                       name="FC (suav.)" if h_is_smooth else "FC (bpm)",
                       mode="lines", yaxis="y6"),
            row=1, col=1
        )

    # Dinámica instantánea (subplot 2)
    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc"], name="ΔTSS (inst)", mode="lines"), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc"], name="ΔFSS (inst)", mode="lines"), row=2, col=1)

    # Layout y ejes
    fig.update_xaxes(title_text="Tiempo (s)", row=2, col=1)
    fig.update_layout(
        title=dict(text=title, x=0.5),
        showlegend=True, template="plotly_white", height=900,
        legend=dict(orientation="h", x=0, y=-0.12),
        margin=dict(l=70, r=250, t=80, b=60),

        # Ejes del subplot 1 (varios overlays a la derecha)
        yaxis1=dict(title="TSS (acum)"),
        yaxis2=dict(title="FSS (acum)", overlaying="y", side="right", position=0.88),
        yaxis3=dict(title="ΔTSS (MA30s)", overlaying="y", side="right", position=0.92),
        yaxis4=dict(title="ΔFSS (MA30s)", overlaying="y", side="right", position=0.96),
        yaxis5=dict(title="Potencia (W)", overlaying="y", side="right", position=1.00),
        yaxis6=dict(overlaying="y", side="right", showticklabels=False),
    )
    return fig


def figure_to_html_bytes(fig) -> bytes:
    buf = StringIO()
    fig.write_html(buf, include_plotlyjs="cdn", full_html=True)
    return buf.getvalue().encode("utf-8")
