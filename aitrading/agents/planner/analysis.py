from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import os
import logfire

from ...tools.bybit.market_data import MarketDataTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator
from ...tools.charts.indicators import IndicatorCalculator

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
                logfire.info("Starting market analysis", symbol=symbol)

                # Get current price and timeframes
                current_price = self.market_data.get_current_price(symbol)
                timeframes = self.market_data.get_analysis_timeframes()
                
                logfire.info("Retrieved market basics", 
                           symbol=symbol,
                           current_price=current_price,
                           timeframes=timeframes)

                # Fetch historical data for all timeframes
                timeframe_data = self._fetch_timeframe_data(symbol, timeframes)

                # Generate analysis results
                volatility_metrics = self._calculate_volatility(timeframe_data)
                if volatility_metrics:
                    logfire.info("Volatility metrics calculated",
                               symbol=symbol,
                               metrics_count=len(volatility_metrics.metrics))

                charts = self._generate_charts(symbol, timeframes, timeframe_data)
                logfire.info("Chart generation completed", 
                           symbol=symbol,
                           charts_count=len(charts))

                analysis_result = {
                    "current_price": current_price,
                    "timeframes": timeframes,
                    "charts": charts,
                    "volatility_metrics": volatility_metrics
                }

                logfire.info("Market analysis completed", 
                           symbol=symbol,
                           has_volatility_metrics=bool(volatility_metrics),
                           charts_generated=len(charts))

                return analysis_result

        except Exception as e:
            logfire.exception("Market analysis failed",
                          symbol=symbol,
                          error=str(e))
            raise

    def _fetch_timeframe_data(self, symbol: str, timeframes: List[str]) -> Dict:
        """Fetch historical data for all timeframes."""
        timeframe_data = {}
        try:
            with logfire.span("fetch_market_data") as span:
                span.set_attribute("symbol", symbol)
                logfire.info("Starting historical data fetch",
                           symbol=symbol,
                           timeframes=timeframes)

                for timeframe in timeframes:
                    try:
                        with logfire.span(f"fetch_{timeframe}_data"):
                            # Fetch raw data
                            df = self.market_data.fetch_historical_data(symbol, timeframe)
                            
                            # Calculate indicators once
                            timeframe_config = self.chart_generator.config.get_timeframe_config(timeframe)
                            calculator = IndicatorCalculator(df)
                            all_indicators = []
                            for view in timeframe_config.views:
                                all_indicators.extend(view.indicators)

                            df_with_indicators = calculator.calculate_all(all_indicators)
                            timeframe_data[timeframe] = df_with_indicators
                            
                            logfire.info(f"Data fetched for {timeframe}",
                                       symbol=symbol,
                                       rows=len(df_with_indicators),
                                       indicators=len(all_indicators))

                    except Exception as e:
                        logfire.error(f"Failed to fetch {timeframe} data",
                                   symbol=symbol,
                                   timeframe=timeframe,
                                   error=str(e))
                        # Continue with other timeframes despite error
                        continue
                
                logfire.info("Historical data fetch completed",
                           symbol=symbol,
                           timeframes_fetched=len(timeframe_data),
                           timeframes_failed=len(timeframes) - len(timeframe_data))

                if not timeframe_data:
                    raise ValueError(f"Failed to fetch data for all timeframes for {symbol}")

                return timeframe_data

        except Exception as e:
            logfire.error("Failed to fetch historical data",
                       symbol=symbol,
                       error=str(e))
            raise

    def _calculate_volatility(self, timeframe_data: Dict) -> Optional[Dict]:
        """Calculate volatility metrics for all timeframes."""
        try:
            with logfire.span("calculate_volatility"):
                metrics = self.volatility_calculator.calculate_for_timeframes(timeframe_data)
                
                # Log detailed metrics for each timeframe
                for timeframe, metric in metrics.metrics.items():
                    logfire.info(f"Volatility metrics for {timeframe}",
                               timeframe=timeframe,
                               regime=metric.regime,
                               atr=metric.atr,
                               opportunity_score=metric.opportunity_score,
                               direction_score=metric.direction_score)
                
                return metrics

        except Exception as e:
            logfire.error("Volatility calculation failed",
                       error=str(e),
                       timeframes=list(timeframe_data.keys()))
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
                    with logfire.span(f"generate_chart_{timeframe}") as span:
                        span.set_attributes({
                            "symbol": symbol,
                            "timeframe": timeframe
                        })

                        logfire.info(f"Generating charts for {timeframe}",
                                   symbol=symbol,
                                   timeframe=timeframe)

                        # Use DataFrame with pre-calculated indicators
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

                            logfire.info(f"Charts generated for {timeframe}",
                                       symbol=symbol,
                                       timeframe=timeframe,
                                       charts_count=len(timeframe_charts))
                        else:
                            logfire.warning(f"No charts generated for {timeframe}",
                                        symbol=symbol,
                                        timeframe=timeframe)

                except Exception as e:
                    logfire.exception(f"Error generating charts for {timeframe}",
                                  symbol=symbol,
                                  timeframe=timeframe,
                                  error=str(e))

            logfire.info("Charts generation completed", 
                        symbol=symbol,
                        total_charts=len(generated_charts),
                        timeframes_processed=len(timeframes))

            return generated_charts

        except Exception as e:
            logfire.exception(f"Error in chart generation",
                          symbol=symbol,
                          error=str(e))
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
        removed_count = 0
        failed_count = 0

        for file in graphs_dir.glob(symbol_pattern):
            try:
                if file.is_file():
                    file.unlink()
                    removed_count += 1
            except Exception as e:
                failed_count += 1
                logfire.warning(f"Could not remove file {file}",
                            symbol=symbol,
                            file=str(file),
                            error=str(e))

        logfire.info("Charts cleanup completed",
                   symbol=symbol,
                   removed=removed_count,
                   failed=failed_count)

    def _save_charts_to_disk(self, charts: List[bytes], symbol: str, 
                           timeframe: str, graphs_dir: Path) -> None:
        """Save generated charts to disk."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_count = 0
        failed_count = 0
        
        for i, chart in enumerate(charts):
            filename = f"{symbol}_{timeframe}_view{i}_{timestamp}.png"
            filepath = graphs_dir / filename
            
            try:
                with open(filepath, 'wb') as f:
                    f.write(chart)
                saved_count += 1
                logfire.debug(f"Saved chart to disk",
                          symbol=symbol,
                          timeframe=timeframe,
                          filename=filename)
            except Exception as e:
                failed_count += 1
                logfire.warning(f"Could not save chart",
                            symbol=symbol,
                            timeframe=timeframe,
                            filename=filename,
                            error=str(e))

        logfire.info("Charts saved to disk",
                   symbol=symbol,
                   timeframe=timeframe,
                   saved=saved_count,
                   failed=failed_count)