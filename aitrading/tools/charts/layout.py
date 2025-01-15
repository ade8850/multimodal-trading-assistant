# aitrading/tools/charts/layout.py

from typing import List, Dict, Tuple
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .models import IndicatorConfig


def create_subplots(indicators: List[IndicatorConfig]) -> Tuple[make_subplots, Dict[str, int]]:
    """Create subplot structure based on indicator configuration.
    
    Returns:
        Tuple containing:
        - The figure with subplots
        - A mapping of indicator types to their row numbers
    """
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
        vertical_spacing=0.02,
        subplot_titles=subplot_titles,
    )
    
    return fig, subplot_mapping


def add_candlesticks(fig: make_subplots, df: pd.DataFrame, colors: dict) -> None:
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
        ),
        row=1,
        col=1,
    )


def add_overlay_indicator(fig: make_subplots, df: pd.DataFrame, indicator: IndicatorConfig,
                         indicator_name: str, colors: dict) -> None:
    """Add an overlay indicator to the main chart."""
    if indicator.type == "ema":
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[indicator_name],
                name=indicator_name,
                line=dict(color=colors[f"ema{indicator.parameters.period}"], width=1),
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
                    name=band.replace("_", " "),
                    line=dict(color=colors["bb_bands"], width=1, dash="dash"),
                ),
                row=1,
                col=1,
            )


def add_volume(fig: make_subplots, df: pd.DataFrame, colors: dict, row: int) -> None:
    """Add volume chart to specified row."""
    colors_vol = [
        colors["volume_up"] if close >= open else colors["volume_down"]
        for open, close in zip(df["open"], df["close"])
    ]

    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume", marker_color=colors_vol),
        row=row,
        col=1,
    )


def add_rsi(fig: make_subplots, df: pd.DataFrame, colors: dict, row: int, 
            params: dict) -> None:
    """Add RSI indicator to specified row."""
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["RSI"],
            name="RSI",
            line=dict(color=colors["rsi"], width=1),
        ),
        row=row,
        col=1,
    )

    # Add RSI levels
    for level in [params.get("oversold", 30), params.get("overbought", 70)]:
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_color=colors["text"],
            opacity=0.5,
            row=row,
        )


def add_macd(fig: make_subplots, df: pd.DataFrame, colors: dict, row: int) -> None:
    """Add MACD indicator to specified row."""
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD"],
            name="MACD",
            line=dict(color=colors["macd_line"], width=1),
        ),
        row=row,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD_signal"],
            name="Signal",
            line=dict(color=colors["signal_line"], width=1),
        ),
        row=row,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["MACD_hist"],
            name="MACD Hist",
            marker_color=[
                colors["macd_hist_pos"]
                if v >= 0
                else colors["macd_hist_neg"]
                for v in df["MACD_hist"]
            ],
        ),
        row=row,
        col=1,
    )


def add_indicators(fig: make_subplots, df: pd.DataFrame, indicators: List[IndicatorConfig],
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


def update_layout(fig: make_subplots, colors: dict, rows: int) -> None:
    """Update chart layout and styling."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        font=dict(color=colors["text"]),
        showlegend=True,
        height=1800,
        width=2560,
        margin=dict(l=100, r=100, t=100, b=100),
    )

    # Calculate domain for each subplot
    spacing = 0.05  # Space between subplots
    available_space = 1.0 - (spacing * (rows - 1))
    main_chart_height = 0.5  # Main chart takes 50% of available space
    other_chart_height = (available_space - main_chart_height) / (rows - 1) if rows > 1 else 0

    # Update y-axis domains
    if rows == 1:
        fig.update_yaxes(domain=[0, 1], row=1, col=1)
    else:
        # Main chart
        fig.update_yaxes(domain=[1 - main_chart_height, 1], row=1, col=1)
        
        # Other charts
        for row in range(2, rows + 1):
            top = 1 - main_chart_height - (spacing * (row - 2)) - (other_chart_height * (row - 2))
            bottom = top - other_chart_height
            fig.update_yaxes(domain=[bottom, top], row=row, col=1)

    # Update grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=colors["grid"])
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=colors["grid"])