# made4try/plots.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import StringIO


def _add_window_band(fig, df, row=None, col=None):
    """Sombrea la ventana seleccionada si existen WIN_start_s / WIN_end_s."""
    if ("WIN_start_s" not in df.columns) or ("WIN_end_s" not in df.columns):
        return
    try:
        w_start = df["WIN_start_s"].iloc[0]
        w_end = df["WIN_end_s"].iloc[0]
        if w_start != w_start or w_end != w_end:
            return
        x0 = float(w_start)
        x1 = float(w_end)
    except Exception:
        return

    try:
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor="rgba(120,120,120,0.18)",
            line_width=0,
            row=row, col=col,
        )
    except Exception:
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor="rgba(120,120,120,0.18)",
            line_width=0,
        )


def _badge(df) -> str:
    """Construye badge corto y estable para no llenar el layout."""
    parts = []
    try:
        if "WIN_mode" in df.columns:
            v = df["WIN_mode"].iloc[0]
            if v == v and str(v).strip():
                parts.append(f"mode={v}")
        if "WIN_mins" in df.columns:
            v = df["WIN_mins"].iloc[0]
            if v == v:
                parts.append(f"win={float(v):.0f}min")
        if "WIN_signal" in df.columns:
            v = df["WIN_signal"].iloc[0]
            if v == v and str(v).strip():
                parts.append(f"signal={v}")
        if "EF_win" in df.columns:
            v = df["EF_win"].iloc[0]
            if v == v:
                parts.append(f"EFR(rel)={float(v):.3f}")
        if "DA_win_pct" in df.columns:
            v = df["DA_win_pct"].iloc[0]
            if v == v:
                parts.append(f"DA={float(v):.2f}%")
    except Exception:
        pass
    return " | ".join(parts)


def make_plot_loads(df, title, show_base=True):
    t = df["elapsed_s"]
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines"))
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines"))

    if show_base:
        if "power_w" in df:
            fig.add_trace(go.Scatter(x=t, y=df["power_w"], name="Potencia (W)", mode="lines", yaxis="y2"))
        if "hr_bpm" in df:
            fig.add_trace(go.Scatter(x=t, y=df["hr_bpm"], name="FC (bpm)", mode="lines", yaxis="y3"))

    _add_window_band(fig, df)

    subtitle = _badge(df)
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            # subtitle evita pelear con plot area y es más estable que annotations
            subtitle=dict(text=subtitle) if subtitle else None,
        ),
        xaxis=dict(title="Tiempo (s)"),
        yaxis=dict(title="Carga acumulada (TSS/FSS)", rangemode="tozero"),
        yaxis2=dict(title="Potencia (W)", overlaying="y", side="right", position=1.0, showgrid=False),
        yaxis3=dict(title="FC (bpm)", overlaying="y", side="right", position=0.98, showgrid=False),
        legend=dict(orientation="h", x=0, y=1.02),
        template="plotly_white",
        margin=dict(l=60, r=90, t=90, b=50),
    )
    return fig


def make_plot_loads_dual(df, title):
    t = df["elapsed_s"]

    # ⚠️ Evitamos subplot_titles porque suele montarse con annotations/titles
    fig = make_subplots(
        rows=2, cols=1,
        vertical_spacing=0.12,
        row_heights=[0.6, 0.4]
    )

    # Row 1
    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc_ma30"], name="ΔTSS (MA30s)", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc_ma30"], name="ΔFSS (MA30s)", mode="lines"), row=1, col=1)

    if "power_ma30" in df:
        fig.add_trace(go.Scatter(x=t, y=df["power_ma30"], name="Potencia (MA30s)", mode="lines"), row=1, col=1)
    if "hr_ma30" in df:
        fig.add_trace(go.Scatter(x=t, y=df["hr_ma30"], name="FC (MA30s)", mode="lines"), row=1, col=1)

    # Row 2
    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc"], name="ΔTSS (inst)", mode="lines"), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc"], name="ΔFSS (inst)", mode="lines"), row=2, col=1)

    fig.update_xaxes(title_text="Tiempo (s)", row=2, col=1)

    _add_window_band(fig, df, row=1, col=1)
    _add_window_band(fig, df, row=2, col=1)

    subtitle = _badge(df)

    # Etiquetas “panel” dentro de cada subplot (no pelean con el título)
    fig.add_annotation(
        text="Carga Acumulada + Promedios (30s)",
        xref="paper", yref="paper",
        x=0.0, y=0.98,
        showarrow=False,
        font=dict(size=12, color="rgba(60,60,60,0.9)")
    )
    fig.add_annotation(
        text="Dinámica Instantánea (ΔTSS/ΔFSS)",
        xref="paper", yref="paper",
        x=0.0, y=0.42,
        showarrow=False,
        font=dict(size=12, color="rgba(60,60,60,0.9)")
    )

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            subtitle=dict(text=subtitle) if subtitle else None,
        ),
        showlegend=True,
        template="plotly_white",
        height=900,
        legend=dict(orientation="h", x=0, y=-0.12),
        margin=dict(l=70, r=90, t=110, b=60),
    )
    return fig


def figure_to_html_bytes(fig) -> bytes:
    buf = StringIO()
    fig.write_html(buf, include_plotlyjs="cdn", full_html=True)
    return buf.getvalue().encode("utf-8")
