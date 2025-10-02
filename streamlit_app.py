import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def make_plot_four_panels(
    df: pd.DataFrame,
    title: str = "Análisis de Carga Fisiológica – Made4Try"
) -> go.Figure:
    """
    Crea 4 paneles verticales independientes para visualizar todas las dinámicas:
    1. Potencia (W)
    2. Frecuencia Cardíaca (bpm)
    3. Eficiencia (EF)
    4. Decoupling Aeróbico (DA)
    """
    t = df["elapsed_s"]
    p = df.get("power_w")
    hr = df.get("hr_bpm")
    
    ef = df.get("ef_power_hr")
    if ef is None:
        ef = (df["power_w"] / df["hr_bpm"].replace({0: pd.NA}))
    
    da = df.get("da")
    if da is None:
        da = ef.diff()
    
    # Pendiente FC (bpm/s)
    dt = pd.Series(t).diff().replace(0, pd.NA).fillna(1)
    fc_slope = pd.Series(hr).diff().fillna(0) / dt
    
    # Crear 4 subplots verticales
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.25, 0.25, 0.25, 0.25],
        subplot_titles=("Potencia", "Frecuencia Cardíaca", "Eficiencia (EF)", "Decoupling Aeróbico (DA)")
    )
    
    # Panel 1: Potencia
    fig.add_trace(
        go.Scatter(x=t, y=p, name="Potencia (W)", mode="lines", 
                   line=dict(color="#1f77b4", width=2)),
        row=1, col=1
    )
    
    # Panel 2: FC y Pendiente FC
    fig.add_trace(
        go.Scatter(x=t, y=hr, name="FC (bpm)", mode="lines",
                   line=dict(color="#ff7f0e", width=2)),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=t, y=fc_slope, name="Pendiente FC (bpm/s)", mode="lines",
                   line=dict(color="#2ca02c", width=1.5)),
        row=2, col=1
    )
    
    # Panel 3: EF
    fig.add_trace(
        go.Scatter(x=t, y=ef, name="EF (W/bpm)", mode="lines",
                   line=dict(color="#9467bd", width=2)),
        row=3, col=1
    )
    
    # Panel 4: DA (con escala independiente)
    fig.add_trace(
        go.Scatter(x=t, y=da, name="DA (ΔEF)", mode="lines",
                   line=dict(color="#d62728", width=2, dash="solid")),
        row=4, col=1
    )
    
    # Añadir línea de referencia en 0 para DA
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5, row=4, col=1)
    
    # Configurar ejes
    fig.update_xaxes(title_text="Tiempo transcurrido (s)", row=4, col=1)
    fig.update_yaxes(title_text="Watts", row=1, col=1)
    fig.update_yaxes(title_text="bpm / bpm/s", row=2, col=1)
    fig.update_yaxes(title_text="W/bpm", row=3, col=1)
    fig.update_yaxes(title_text="ΔEF", row=4, col=1)
    
    fig.update_layout(
        title=title,
        height=1000,
        showlegend=True,
        legend=dict(orientation="h", x=0, y=1.02, xanchor="left"),
        template="plotly_white",
        margin=dict(l=60, r=30, t=100, b=50),
    )
    
    return fig


def make_plot_adaptive_dual_panel(
    df: pd.DataFrame,
    title: str = "Análisis de Carga Fisiológica – Made4Try"
) -> go.Figure:
    """
    Versión mejorada de 2 paneles con DA en escala independiente.
    Panel superior: Potencia + FC
    Panel inferior: EF + DA (con eje secundario para DA)
    """
    t = df["elapsed_s"]
    p = df.get("power_w")
    hr = df.get("hr_bpm")
    
    ef = df.get("ef_power_hr")
    if ef is None:
        ef = (df["power_w"] / df["hr_bpm"].replace({0: pd.NA}))
    
    da = df.get("da")
    if da is None:
        da = ef.diff()
    
    # Pendiente FC
    dt = pd.Series(t).diff().replace(0, pd.NA).fillna(1)
    fc_slope = pd.Series(hr).diff().fillna(0) / dt
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.55, 0.45],
        specs=[[{"secondary_y": True}], [{"secondary_y": True}]]
    )
    
    # Panel superior: Potencia (izq) + FC/Pendiente (der)
    fig.add_trace(
        go.Scatter(x=t, y=p, name="Potencia (W)", mode="lines",
                   line=dict(color="#1f77b4", width=2)),
        row=1, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=t, y=hr, name="FC (bpm)", mode="lines",
                   line=dict(color="#ff7f0e", width=2)),
        row=1, col=1, secondary_y=True
    )
    fig.add_trace(
        go.Scatter(x=t, y=fc_slope, name="Pendiente FC", mode="lines",
                   line=dict(color="#2ca02c", width=1.5)),
        row=1, col=1, secondary_y=True
    )
    
    # Panel inferior: EF (izq) + DA (der, escala independiente)
    fig.add_trace(
        go.Scatter(x=t, y=ef, name="EF (W/bpm)", mode="lines",
                   line=dict(color="#9467bd", width=2)),
        row=2, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=t, y=da, name="DA (ΔEF)", mode="lines",
                   line=dict(color="#d62728", width=2)),
        row=2, col=1, secondary_y=True
    )
    
    # Títulos de ejes
    fig.update_xaxes(title_text="Tiempo transcurrido (s)", row=2, col=1)
    fig.update_yaxes(title_text="Potencia (W)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="FC / Pendiente FC", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="EF (W/bpm)", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="DA (ΔEF)", row=2, col=1, secondary_y=True)
    
    fig.update_layout(
        title=title,
        height=700,
        legend=dict(orientation="h", x=0, y=1.08),
        template="plotly_white",
        margin=dict(l=60, r=60, t=100, b=50),
    )
    
    return fig


# ==== INTEGRACIÓN EN TU CÓDIGO EXISTENTE ====
# Reemplaza tus funciones make_plot_dual_panel y make_plot_three_axes
# con estas nuevas funciones.

# En la sección donde llamas render_plot_and_download, agrega una opción:
# 
# chart_mode = st.radio(
#     "Modo de visualización",
#     options=[
#         "4 paneles independientes (mejor para DA)",
#         "2 paneles con DA en eje secundario", 
#         "2 paneles clásicos",
#         "Eje terciario (1 panel)"
#     ],
#     index=0
# )
#
# Y en render_plot_and_download:
# if "4 paneles" in chart_mode:
#     fig = make_plot_four_panels(df)
# elif "DA en eje secundario" in chart_mode:
#     fig = make_plot_adaptive_dual_panel(df)
# elif "2 paneles clásicos" in chart_mode:
#     fig = make_plot_dual_panel(df, ...)  # tu función original
# else:
#     fig = make_plot_three_axes(df, ...)  # tu función original
