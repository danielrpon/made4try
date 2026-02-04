# Figuras Plotly (básica y dual)
# plots.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import StringIO


def _get_window_info(df):
    """
    Extrae ventana seleccionada y metadata desde la primera fila.
    Devuelve (start_s, end_s, label_text) o (None, None, None).
    """
    try:
        if df is None or len(df) == 0:
            return None, None, None

        # Ventana en primera fila
        start = df["WIN_start_s"].iloc[0] if "WIN_start_s" in df.columns else None
        end = df["WIN_end_s"].iloc[0] if "WIN_end_s" in df.columns else None

        if start is None or end is None:
            return None, None, None

        # Asegura float
        start = float(start)
        end = float(end)

        # Label opcional
        mode = df["WIN_mode"].iloc[0] if "WIN_mode" in df.columns else None
        mins = df["WIN_mins"].iloc[0] if "WIN_mins" in df.columns else None
        sig = df["WIN_signal"].iloc[0] if "WIN_signal" in df.columns else None

        ef = df["EF_win"].iloc[0] if "EF_win" in df.columns else None
        da = df["DA_win_pct"].iloc[0] if "DA_win_pct" in df.columns else None

        parts = []
        if mode is not None and str(mode) != "nan":
            parts.append(f"mode={mode}")
        if mins is not None and str(mins) != "nan":
            try:
                parts.append(f"win={float(mins):.0f}min")
            except Exception:
                parts.append(f"win={mins}")
        if sig is not None and str(sig) != "nan":
            parts.append(f"signal={sig}")

        # EF/DA (si existen)
        if ef is not None and str(ef) != "nan":
            try:
                parts.append(f"EF={float(ef):.4f}")
            except Exception:
                pass
        if da is not None and str(da) != "nan":
            try:
                parts.append(f"DA={float(da):.2f}%")
            except Exception:
                pass

        label = " | ".join(parts) if parts else "Ventana seleccionada"
        return start, end, label

    except Exception:
        return None, None, None


def _add_window_highlight(fig, start_s, end_s, label_text=None, *, row=None, col=None):
    """
    Agrega banda sombreada y etiqueta. Soporta figures simples o subplots.
    """
    try:
        if start_s is None or end_s is None:
            return

        # Banda sombreada
        fig.add_vrect(
            x0=start_s,
            x1=end_s,
            fillcolor="rgba(0, 0, 0, 0.10)",  # gris translúcido
            line_width=0,
            layer="below",
            row=row,
            col=col,
        )

        # Etiqueta cerca del borde superior del subplot
        if label_text:
            fig.add_annotation(
                x=start_s,
                y=1.02,
                xref="x",
                yref="paper",
                text=label_text,
                showarrow=False,
                align="left",
                font=dict(size=12),
            )
    except Exception:
        # No bloquear por gráficos
        return


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

    # Ventana resaltada (si existe)
    w0, w1, wlab = _get_window_info(df)
    if w0 is not None and w1 is not None:
        _add_window_highlight(fig, w0, w1, wlab)

    fig.update_layout(
        title=title,
        xaxis=dict(title="Tiempo (s)"),
        yaxis=dict(title="Carga acumulada (TSS/FSS)", rangemode="tozero"),
        yaxis2=dict(title="Potencia (W)", overlaying="y", side="right", position=1.0, showgrid=False),
        yaxis3=dict(title="FC (bpm)", overlaying="y", side="right", position=0.98, showgrid=False),
        legend=dict(orientation="h", x=0, y=1.12),
        template="plotly_white",
        margin=dict(l=60, r=80, t=70, b=50),
    )
    return fig


def make_plot_loads_dual(df, title):
    t = df["elapsed_s"]
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Carga Acumulada + Promedios (30s)", "Dinámica Instantánea (ΔTSS/ΔFSS)"),
        vertical_spacing=0.12,
        row_heights=[0.6, 0.4],
    )

    fig.add_trace(go.Scatter(x=t, y=df["TSS"], name="TSS (acum)", mode="lines", yaxis="y1"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS"], name="FSS (acum)", mode="lines", yaxis="y2"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc_ma30"], name="ΔTSS (MA30s)", mode="lines", yaxis="y3"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc_ma30"], name="ΔFSS (MA30s)", mode="lines", yaxis="y4"), row=1, col=1)

    if "power_ma30" in df:
        fig.add_trace(go.Scatter(x=t, y=df["power_ma30"], name="Potencia (MA30s)", mode="lines", yaxis="y5"), row=1, col=1)
    if "hr_ma30" in df:
        fig.add_trace(go.Scatter(x=t, y=df["hr_ma30"], name="FC (MA30s)", mode="lines", yaxis="y6"), row=1, col=1)

    fig.add_trace(go.Scatter(x=t, y=df["TSS_inc"], name="ΔTSS (inst)", mode="lines"), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=df["FSS_inc"], name="ΔFSS (inst)", mode="lines"), row=2, col=1)

    # Ventana resaltada (si existe): ponerla en ambos subplots
    w0, w1, wlab = _get_window_info(df)
    if w0 is not None and w1 is not None:
        _add_window_highlight(fig, w0, w1, wlab, row=1, col=1)
        _add_window_highlight(fig, w0, w1, None, row=2, col=1)

    fig.update_xaxes(title_text="Tiempo (s)", row=2, col=1)
    fig.update_layout(
        title=dict(text=title, x=0.5),
        showlegend=True,
        template="plotly_white",
        height=900,
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
