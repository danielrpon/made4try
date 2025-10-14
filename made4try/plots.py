# Figuras Plotly (básica y dual)
# made4try/plots.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import StringIO

def _get_series(df, smooth_name, raw_name):
    """Devuelve serie suavizada si existe; si no, la cruda (o None)."""
    if smooth_name in df.columns:
        return df[smooth_name]
    if raw_name in df.columns:
        return df[raw_name]
    return None

def make_plot_loads(df, title, show_base=True):
    t = df["elapsed_s"]
    fig = go.Figure()

    # Cargas acumuladas
    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines"))
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines"))

    # Señales base (preferir suavizadas)
    if show_base:
        pw = _get_series(df, "power_smooth", "power_w")
        hr = _get_series(df, "hr_smooth",    "hr_bpm")

        if pw is not None:
            fig.add_trace(go.Scatter(
                x=t, y=pw, name="Potencia (suav.)" if "power_smooth" in df.columns else "Potencia (W)",
                mode="lines", yaxis="y2"
            ))
        if hr is not None:
            fig.add_trace(go.Scatter(
                x=t, y=hr, name="FC (suav.)" if "hr_smooth" in df.columns else "FC (bpm)",
                mode="lines", yaxis="y3"
            ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Tiempo (s)"),
        yaxis=dict(title="Carga acumulada (TSS/FSS)", rangemode="tozero"),
        yaxis2=dict(title="Potencia (W)", overlaying="y", side="right", position=1.0, showgrid=False),
        yaxis3=dict(title="FC (bpm)",     overlaying="y", side="right", position=0.98, showgrid=False),
        legend=dict(orientation="h", x=0, y=1.12),
        template="plotly_white",
        margin=dict(l=60, r=80, t=70, b=50),
    )
    return fig

def make_plot_loads_dual(df, title):
    t = df["elapsed_s"]
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Carga Acumulada + Promedios (30s)",
                        "Dinámica Instantánea (ΔTSS/ΔFSS)"),
        vertical_spacing=0.12, row_heights=[0.6, 0.4]
    )

    # Acumulados + promedios de incrementos
    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines", yaxis="y1"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines", yaxis="y2"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc_ma30"], name="ΔTSS (MA30s)", mode="lines", yaxis="y3"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc_ma30"], name="ΔFSS (MA30s)", mode="lines", yaxis="y4"), row=1, col=1)

    # Señales base en la parte superior: preferir suavizadas; si no hay, usar MA30 si existe
    pw = _get_series(df, "power_smooth", "power_ma30" if "power_ma30" in df.columns else "power_w")
    hr = _get_series(df, "hr_smooth",    "hr_ma30"    if "hr_ma30"    in df.columns else "hr_bpm")

    if pw is not None:
        fig.add_trace(go.Scatter(
            x=t, y=pw, name="Potencia (suav.)" if "power_smooth" in df.columns else
                         ("Potencia (MA30s)" if "power_ma30" in df.columns else "Potencia (W)"),
            mode="lines", yaxis="y5"
        ), row=1, col=1)

    if hr is not None:
        fig.add_trace(go.Scatter(
            x=t, y=hr, name="FC (suav.)" if "hr_smooth" in df.columns else
                         ("FC (MA30s)" if "hr_ma30" in df.columns else "FC (bpm)"),
            mode="lines", yaxis="y6"
        ), row=1, col=1)

    # Incrementos instante a instante
    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc"], name="ΔTSS (inst)", mode="lines"), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc"], name="ΔFSS (inst)", mode="lines"), row=2, col=1)

    fig.update_xaxes(title_text="Tiempo (s)", row=2, col=1)
    fig.update_layout(
        title=dict(text=title, x=0.5),
        showlegend=True, template="plotly_white", height=900,
        legend=dict(orientation="h", x=0, y=-0.12),
        margin=dict(l=70, r=250, t=80, b=60),
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
