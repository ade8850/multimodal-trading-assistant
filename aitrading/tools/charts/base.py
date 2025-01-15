# aitrading/tools/charts/base.py

import base64
from typing import List, Dict, Any
import pandas as pd
from plotly.subplots import make_subplots

from .indicators import calculate_indicators
from .layout import (
    create_subplots, add_candlesticks, 
    add_indicators, update_layout
)
from .config import TimeframesConfiguration
from .utils import fig_to_image, chart_colors


class ChartGeneratorTool:
    """Tool for generating technical analysis charts."""

    def __init__(self):
        self.colors = chart_colors()
        self.config = TimeframesConfiguration()

    def create_chart(self, df: pd.DataFrame, timeframe: str) -> bytes:
        """Generate a complete technical analysis chart."""
        try:
            # Get configuration for this timeframe
            timeframe_config = self.config.get_timeframe_config(timeframe)
            
            # Calculate indicators
            df_indicators = calculate_indicators(df)

            # Create figure with dynamic subplots
            fig, subplot_mapping = create_subplots(timeframe_config.indicators)

            # Add candlesticks
            add_candlesticks(fig, df_indicators, self.colors)

            # Add all indicators
            add_indicators(
                fig=fig,
                df=df_indicators,
                indicators=timeframe_config.indicators,
                subplot_mapping=subplot_mapping,
                colors=self.colors
            )

            # Update layout with correct number of rows
            update_layout(fig, self.colors, len(subplot_mapping))

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