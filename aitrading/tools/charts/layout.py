# aitrading/tools/charts/layout.py

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def add_candlesticks(fig: make_subplots, df: pd.DataFrame, colors: dict) -> None:
    """Add candlestick chart and overlays."""
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

    # Add EMAs
    for name, color in [
        ("EMA20", "ema20"),
        ("EMA50", "ema50"),
        ("EMA200", "ema200"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[name],
                name=name,
                line=dict(color=colors[color], width=1),
            ),
            row=1,
            col=1,
        )

    # Add Bollinger Bands
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

def add_volume(fig: make_subplots, df: pd.DataFrame, colors: dict) -> None:
    """Add volume chart."""
    colors_vol = [
        colors["volume_up"] if close >= open else colors["volume_down"]
        for open, close in zip(df["open"], df["close"])
    ]

    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume", marker_color=colors_vol),
        row=2,
        col=1,
    )

def add_indicators(fig: make_subplots, df: pd.DataFrame, colors: dict) -> None:
    """Add RSI and MACD indicators."""
    # Add RSI
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["RSI"],
            name="RSI",
            line=dict(color=colors["rsi"], width=1),
        ),
        row=3,
        col=1,
    )

    # Add RSI levels
    for level in [30, 70]:
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_color=colors["text"],
            opacity=0.5,
            row=3,
        )

    # Add MACD
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD"],
            name="MACD",
            line=dict(color=colors["macd_line"], width=1),
        ),
        row=4,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD_signal"],
            name="Signal",
            line=dict(color=colors["signal_line"], width=1),
        ),
        row=4,
        col=1,
    )

    # Add MACD histogram
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
        row=4,
        col=1,
    )

def update_layout(fig: make_subplots, colors: dict) -> None:
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

    # Update axes domains
    fig.update_yaxes(domain=[0.55, 1.0], row=1, col=1)
    fig.update_yaxes(domain=[0.35, 0.50], row=2, col=1)
    fig.update_yaxes(domain=[0.20, 0.30], row=3, col=1)
    fig.update_yaxes(domain=[0.05, 0.15], row=4, col=1)

    # Update grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=colors["grid"])
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=colors["grid"])

    # Update titles
    fig.update_yaxes(title="Price", row=1, col=1)
    fig.update_yaxes(title="Volume", row=2, col=1)
    fig.update_yaxes(title="RSI", range=[0, 100], row=3, col=1)
    fig.update_yaxes(title="MACD", row=4, col=1)