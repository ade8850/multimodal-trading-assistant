# aitrading/tools/charts/base.py

import base64
from typing import List, Dict, Any, Tuple
import pandas as pd
from plotly.subplots import make_subplots
import logging

from .indicators import IndicatorCalculator
from .layout import (
    create_subplots, add_candlesticks, 
    add_indicators, update_layout
)
from .models import ChartView
from .config import TimeframesConfiguration
from .utils import fig_to_image, chart_colors

logger = logging.getLogger("trader")

class ChartGeneratorTool:
    """Tool for generating technical analysis charts."""

    def __init__(self):
        self.colors = chart_colors()
        self.config = TimeframesConfiguration()

    def create_charts_for_timeframe(self, df: pd.DataFrame, timeframe: str) -> List[bytes]:
        """Generate all chart views for a specific timeframe."""
        try:
            # Get configuration for this timeframe
            timeframe_config = self.config.get_timeframe_config(timeframe)
            
            # Calculate all indicators once
            calculator = IndicatorCalculator(df)
            all_indicators = []
            for view in timeframe_config.views:
                all_indicators.extend(view.indicators)
            df_with_indicators = calculator.calculate_all(all_indicators)
            
            # Generate a chart for each view
            charts = []
            for view in timeframe_config.views:
                try:
                    chart_bytes = self._create_view_chart(
                        df=df_with_indicators,
                        view=view,
                        timeframe=timeframe
                    )
                    charts.append(chart_bytes)
                except Exception as e:
                    logger.error(f"Error generating {view.name} chart for {timeframe}: {str(e)}")
                    
            return charts

        except Exception as e:
            logger.error(f"Error generating charts for {timeframe}: {str(e)}")
            raise

    def _create_view_chart(self, df: pd.DataFrame, view: ChartView, timeframe: str) -> bytes:
        """Generate a single view chart."""
        try:
            # Create figure with dynamic subplots for this view
            fig, subplot_mapping = create_subplots(view.indicators)

            # Add candlesticks
            add_candlesticks(fig, df, self.colors)

            # Add indicators for this view
            add_indicators(
                fig=fig,
                df=df,
                indicators=view.indicators,
                subplot_mapping=subplot_mapping,
                colors=self.colors
            )

            # Update layout
            update_layout(
                fig=fig,
                colors=self.colors,
                rows=len(subplot_mapping),
                title=view.title
            )

            return fig_to_image(fig)

        except Exception as e:
            raise Exception(f"Error generating {view.name} chart: {str(e)}")

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