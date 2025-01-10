# aitrading/tools/charts/base.py

import base64
from typing import List, Dict, Any
import pandas as pd
from plotly.subplots import make_subplots

from .indicators import calculate_indicators
from .layout import update_layout, add_candlesticks, add_volume, add_indicators
from .utils import fig_to_image, chart_colors


class ChartGeneratorTool:
    """Tool for generating technical analysis charts."""

    def __init__(self):
        self.colors = chart_colors()

    def create_chart(self, df: pd.DataFrame, timeframe: str) -> bytes:
        """Generate a complete technical analysis chart."""
        try:
            df_indicators = calculate_indicators(df)
            fig = self._build_chart(df_indicators, timeframe)
            return fig_to_image(fig)
        except Exception as e:
            raise Exception(f"Error generating chart: {str(e)}")

    def get_base64_charts(self, charts: List[bytes]) -> List[Dict[str, Any]]:
        """Convert chart images to base64 format for Claude."""
        return [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(img).decode("utf-8"),
            },
        } for img in charts]

    def _build_chart(self, df: pd.DataFrame, timeframe: str) -> make_subplots:
        """Build the complete chart with all indicators."""
        fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            subplot_titles=(f"{timeframe}", "Volume", "RSI", "MACD"),
        )

        add_candlesticks(fig, df, self.colors)
        add_volume(fig, df, self.colors)
        add_indicators(fig, df, self.colors)
        update_layout(fig, self.colors)

        return fig
