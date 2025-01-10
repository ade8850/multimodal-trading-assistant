# aitrading/tools/charts/utils.py

from typing import Dict
import plotly.graph_objects as go

def chart_colors() -> Dict[str, str]:
    """Get chart color scheme."""
    return {
        "background": "#1E1E1E",
        "grid": "#2D2D2D",
        "text": "#E0E0E0",
        "candle_up": "#26A69A",
        "candle_down": "#EF5350",
        "volume_up": "rgba(38, 166, 154, 0.5)",
        "volume_down": "rgba(239, 83, 80, 0.5)",
        "ema20": "#3B82F6",
        "ema50": "#F59E0B",
        "ema200": "#8B5CF6",
        "bb_bands": "rgba(255, 255, 255, 0.3)",
        "rsi": "#E879F9",
        "macd_line": "#60A5FA",
        "signal_line": "#FBBF24",
        "macd_hist_pos": "rgba(38, 166, 154, 0.7)",
        "macd_hist_neg": "rgba(239, 83, 80, 0.7)",
    }

def fig_to_image(fig: go.Figure) -> bytes:
    """Convert figure to PNG bytes."""
    return fig.to_image(format="png", width=2560, height=1800, scale=2)