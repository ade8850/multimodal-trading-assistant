from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import os
import logfire

from ...tools.bybit.market_data import MarketDataTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator

class MarketAnalyzer:
    """Handles market data analysis, chart generation and volatility calculations."""

    def __init__(self, 
                 market_data: MarketDataTool, 
                 chart_generator: ChartGeneratorTool,
                 volatility_calculator: VolatilityCalculator):
        """Initialize the market analyzer.
        
        Args:
            market_data: Service for market data operations
            chart_generator: Service for chart generation
            volatility_calculator: Service for volatility metrics
        """
        self.market_data = market_data
        self.chart_generator = chart_generator
        self.volatility_calculator = volatility_calculator

    def analyze_market(self, symbol: str) -> Dict:
        """Perform complete market analysis for a symbol.
        
        Args:
            symbol: Trading symbol to analyze
            
        Returns:
            Dict containing:
                - current_price: Current market price
                - timeframes: List of analyzed timeframes
                - charts: Generated chart images
                - volatility_metrics: Volatility analysis
        """
        try:
            with logfire.span("market_analysis") as span:
                span.set_attribute("symbol", symbol)

                # Get current price and timeframes
                current_price = self.market_data.get_current_price(symbol)
                timeframes = self.market_data.get_analysis_timeframes()

                # Fetch historical data for all timeframes
                timeframe_data = self._fetch_timeframe_data(symbol, timeframes)

                # Generate analysis results
                volatility_metrics = self._calculate_volatility(timeframe_data)
                charts = self._generate_charts(symbol, timeframes, timeframe_data)

                logfire.info("Market analysis completed", 
                           symbol=symbol,
                           timeframes=timeframes,
                           charts_count=len(charts))

                return {
                    "current_price": current_price,
                    "timeframes": timeframes,
                    "charts": charts,
                    "volatility_metrics": volatility_metrics
                }

        except Exception as e:
            logfire.exception("Market analysis failed", error=str(e))
            raise

    def _fetch_timeframe_data(self, symbol: str, timeframes: List[str]) -> Dict:
        """Fetch historical data for all timeframes."""
        timeframe_data = {}
        try:
            with logfire.span("fetch_market_data"):
                for timeframe in timeframes:
                    df = self.market_data.fetch_historical_data(symbol, timeframe)
                    timeframe_data[timeframe] = df
                logfire.info("Historical data fetched", 
                           symbol=symbol,
                           timeframes=timeframes)
                return timeframe_data
        except Exception as e:
            logfire.error("Failed to fetch historical data", error=str(e))
            raise

    def _calculate_volatility(self, timeframe_data: Dict) -> Optional[Dict]:
        """Calculate volatility metrics for all timeframes."""
        try:
            with logfire.span("calculate_volatility"):
                metrics = self.volatility_calculator.calculate_for_timeframes(timeframe_data)
                logfire.info("Volatility metrics calculated")
                return metrics
        except Exception as e:
            logfire.error("Volatility calculation failed", error=str(e))
            return None

    def _generate_charts(self, symbol: str, timeframes: List[str], timeframe_data: Dict) -> List[bytes]:
        """Generate technical analysis charts for each timeframe."""
        generated_charts = []
        dump_charts = os.getenv('DUMP_CHARTS', '').lower() in ('true', '1', 'yes')

        try:
            # Setup charts directory
            graphs_dir = self._setup_charts_directory()
            self._cleanup_old_charts(graphs_dir, symbol)

            # Generate charts for each timeframe
            for timeframe in timeframes:
                try:
                    with logfire.span(f"generate_chart_{timeframe}"):
                        df = timeframe_data[timeframe]
                        timeframe_charts = self.chart_generator.create_charts_for_timeframe(df, timeframe)
                        
                        if timeframe_charts:
                            generated_charts.extend(timeframe_charts)
                            
                            if dump_charts:
                                self._save_charts_to_disk(
                                    charts=timeframe_charts,
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    graphs_dir=graphs_dir
                                )

                except Exception as e:
                    logfire.exception(f"Error generating charts for {timeframe}: {str(e)}")

            logfire.info("Charts generation completed", 
                        charts_count=len(generated_charts),
                        symbol=symbol,
                        timeframes=timeframes)

            return generated_charts

        except Exception as e:
            logfire.exception(f"Error in chart generation: {str(e)}")
            return generated_charts  # Return any charts we managed to generate

    def _setup_charts_directory(self) -> Path:
        """Create and setup the charts directory."""
        graphs_dir = Path('.graphs')
        graphs_dir.mkdir(exist_ok=True)
        return graphs_dir

    def _cleanup_old_charts(self, graphs_dir: Path, symbol: str) -> None:
        """Clean up old chart files for the symbol."""
        if not graphs_dir.exists():
            return

        symbol_pattern = f"{symbol}_*"
        for file in graphs_dir.glob(symbol_pattern):
            try:
                if file.is_file():
                    file.unlink()
            except Exception as e:
                logfire.warning(f"Could not remove file {file}: {str(e)}")

        logfire.debug(f"Cleaned up old charts for {symbol}")

    def _save_charts_to_disk(self, charts: List[bytes], symbol: str, 
                           timeframe: str, graphs_dir: Path) -> None:
        """Save generated charts to disk."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for i, chart in enumerate(charts):
            filename = f"{symbol}_{timeframe}_view{i}_{timestamp}.png"
            filepath = graphs_dir / filename
            
            try:
                with open(filepath, 'wb') as f:
                    f.write(chart)
                logfire.debug(f"Saved chart: {filename}")
            except Exception as e:
                logfire.warning(f"Could not save chart {filename}: {str(e)}")
