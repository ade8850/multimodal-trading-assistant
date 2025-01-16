# aitrading/tools/charts/layout.py

from typing import List, Dict, Tuple
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .models import IndicatorConfig
from .utils import get_ema_color


def create_subplots(indicators: List[IndicatorConfig]) -> Tuple[go.Figure, Dict[str, int]]:
    """Create subplot structure based on indicator configuration."""
    # Count how many subplots we need (one for candlesticks + one for each indicator with subplot=True)
    subplot_count = 1 + sum(1 for ind in indicators if ind.subplot)
    
    # Create subplot titles starting with main chart
    subplot_titles = ["Price"]
    subplot_mapping = {"main": 1}  # Maps indicator types to subplot rows
    current_row = 2
    
    # Add subplot titles and mapping for each indicator that needs its own subplot
    for indicator in indicators:
        if indicator.subplot:
            subplot_titles.append(indicator.type.upper())
            subplot_mapping[indicator.type] = current_row
            current_row += 1
    
    # Create the figure with subplots
    fig = make_subplots(
        rows=subplot_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,  # Reduced spacing between subplots
        subplot_titles=subplot_titles,
        row_heights=[0.6] + [0.4/(subplot_count-1)]*(subplot_count-1) if subplot_count > 1 else [1]  # Main chart gets 60% height
    )
    
    return fig, subplot_mapping


def add_candlesticks(fig: go.Figure, df: pd.DataFrame, colors: dict) -> None:
    """Add candlestick chart."""
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color=colors["candle_up"],
            decreasing_line_color=colors["candle_down"],
            name="Price",
            showlegend=True
        ),
        row=1,
        col=1,
    )


def add_overlay_indicator(fig: go.Figure, df: pd.DataFrame, indicator: IndicatorConfig,
                         indicator_name: str, colors: dict) -> None:
    """Add an overlay indicator to the main chart."""
    if indicator.type == "ema":
        period = indicator.parameters.period
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[indicator_name],
                name=f"EMA ({period})",  # Migliorata descrizione
                line=dict(color=get_ema_color(period), width=2),  # Increased line width
                showlegend=True
            ),
            row=1,
            col=1,
        )
    elif indicator.type == "bollinger":
        for band in ["BB_upper", "BB_middle", "BB_lower"]:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[band],
                    name=band.replace("_", " ").replace("BB ", "Bollinger "),  # Nome più descrittivo
                    line=dict(color=colors["bb_bands"], width=1.5, dash="dash"),
                    showlegend=True
                ),
                row=1,
                col=1,
            )


def add_volume(fig: go.Figure, df: pd.DataFrame, colors: dict, row: int) -> None:
    """Add volume chart to specified row."""
    colors_vol = [
        colors["volume_up"] if close >= open else colors["volume_down"]
        for open, close in zip(df["open"], df["close"])
    ]

    fig.add_trace(
        go.Bar(
            x=df.index, 
            y=df["volume"], 
            name="Volume", 
            marker_color=colors_vol,
            showlegend=True
        ),
        row=row,
        col=1,
    )


def add_rsi(fig: go.Figure, df: pd.DataFrame, colors: dict, row: int, 
            params: dict) -> None:
    """Add RSI indicator to specified row."""
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["RSI"],
            name=f"RSI ({params.get('period', 14)})",  # Added period info
            line=dict(color=colors["rsi"], width=2),
            showlegend=True
        ),
        row=row,
        col=1,
    )

    # Add RSI levels with labels
    for level in [params.get("oversold", 30), params.get("overbought", 70)]:
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_color=colors["text"],
            opacity=0.7,
            row=row,
            annotation_text=f"RSI {level}",
            annotation_position="right"
        )


def add_macd(fig: go.Figure, df: pd.DataFrame, colors: dict, row: int) -> None:
    """Add MACD indicator to specified row."""
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD"],
            name="MACD Line",  # Nome più descrittivo
            line=dict(color=colors["macd_line"], width=2),
            showlegend=True
        ),
        row=row,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD_signal"],
            name="Signal Line",  # Nome più descrittivo
            line=dict(color=colors["signal_line"], width=2),
            showlegend=True
        ),
        row=row,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["MACD_hist"],
            name="MACD Histogram",  # Nome più descrittivo
            marker_color=[
                colors["macd_hist_pos"]
                if v >= 0
                else colors["macd_hist_neg"]
                for v in df["MACD_hist"]
            ],
            showlegend=True
        ),
        row=row,
        col=1,
    )


def add_indicators(fig: go.Figure, df: pd.DataFrame, indicators: List[IndicatorConfig],
                  subplot_mapping: Dict[str, int], colors: dict) -> None:
    """Add all indicators based on their configuration."""
    for indicator in indicators:
        if indicator.overlay:
            # For overlays like EMA and Bollinger Bands
            indicator_name = f"EMA{indicator.parameters.period}" if indicator.type == "ema" else indicator.type
            add_overlay_indicator(fig, df, indicator, indicator_name, colors)
        else:
            # For indicators with their own subplot
            row = subplot_mapping.get(indicator.type)
            if not row:
                continue
                
            if indicator.type == "volume":
                add_volume(fig, df, colors, row)
            elif indicator.type == "rsi":
                add_rsi(fig, df, colors, row, indicator.parameters.dict())
            elif indicator.type == "macd":
                add_macd(fig, df, colors, row)


def update_layout(fig: go.Figure, colors: dict, rows: int, title: str = "") -> None:
    """Update chart layout and styling."""
    fig.update_layout(
        margin=dict(l=100, r=200, t=100, b=50),  # Aumentato il margine destro per la legenda

        title=dict(
            text=title,
            x=0.02,            # Spostato a sinistra
            y=0.98,            # In alto
            xanchor='left',    # Ancorato a sinistra
            yanchor='top',
            font=dict(size=28, color=colors["text"])
        ),
        template="plotly_dark",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        font=dict(
            color=colors["text"],
            size=16
        ),
        showlegend=True,
        legend=dict(
            orientation="v",     # Legenda verticale
            y=0.5,              # Centro verticalmente
            x=1.05,             # Fuori dal grafico
            bgcolor='rgba(0,0,0,0.9)',
            bordercolor=colors["grid"],
            borderwidth=1,
            font=dict(
                size=16,
                color=colors["text"]
            ),
            itemsizing='constant',
            itemwidth=40,
            itemclick=False,
            itemdoubleclick=False,
            xanchor='left',     # Ancora a sinistra del punto x
            yanchor='middle',   # Ancora al centro del punto y
            traceorder='grouped'
        ),
        height=3000,
        width=2560,
        xaxis_rangeslider_visible=False,
        grid=dict(
            rows=rows,
            columns=1,
            pattern='independent'
        )
    )

    # Update price chart (first subplot)
    fig.update_yaxes(
        title="Price",
        title_font=dict(size=16),
        tickfont=dict(size=14),
        showgrid=True,
        gridwidth=1,
        gridcolor=colors["grid"],
        griddash='dot',           # Griglia punteggiata
        dtick=500,                # Intervallo della griglia (da adattare al range di prezzi)
        minor=dict(               # Griglia secondaria
            showgrid=True,
            gridwidth=0.5,
            dtick=100,            # Intervallo minore
            gridcolor=colors["grid"]
        ),
        row=1,
        col=1
    )

    # Update other subplots
    for i in range(2, rows + 1):
        fig.update_yaxes(
            title_font=dict(size=16),
            tickfont=dict(size=14),
            showgrid=True,
            gridwidth=1,
            gridcolor=colors["grid"],
            griddash='dot',
            row=i,
            col=1
        )

    # Update all x axes
    for i in range(1, rows + 1):
        is_last = (i == rows)
        fig.update_xaxes(
            title="Date" if is_last else None,
            title_font=dict(size=16),
            tickfont=dict(size=14),
            showgrid=True,
            gridwidth=1,
            gridcolor=colors["grid"],
            griddash='dot',
            dtick="D1",           # Griglia giornaliera
            minor=dict(           # Griglia secondaria per le ore
                showgrid=True,
                gridwidth=0.5,
                dtick="H6",       # Ogni 6 ore
                gridcolor=colors["grid"]
            ),
            row=i,
            col=1
        )