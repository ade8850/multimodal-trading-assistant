# aitrading/tools/charts/utils.py

from typing import Dict
import plotly.graph_objects as go

# Palette di colori per gli EMA
EMA_COLORS = [
    "#3B82F6",  # Blu
    "#F59E0B",  # Arancione
    "#8B5CF6",  # Viola
    "#EC4899",  # Rosa
    "#10B981",  # Verde
    "#6366F1"   # Indigo
]

def get_ema_color(period: int) -> str:
    """Get color for EMA based on period.
    
    Args:
        period: EMA period
    
    Returns:
        Color from the EMA palette
    """
    # Usa il periodo come indice nella palette, con wrap-around
    return EMA_COLORS[period % len(EMA_COLORS)]

def chart_colors() -> Dict[str, str]:
    """Get chart color scheme."""
    return {
        # Background and grid
        "background": "#1E1E1E",
        "grid": "#2D2D2D",
        "text": "#E0E0E0",
        
        # Candlesticks and volume
        "candle_up": "#26A69A",
        "candle_down": "#EF5350",
        "volume_up": "rgba(38, 166, 154, 0.5)",
        "volume_down": "rgba(239, 83, 80, 0.5)",
        
        # Altri indicatori
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