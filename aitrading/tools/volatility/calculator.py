# aitrading/tools/volatility/calculator.py

from typing import Dict
import logfire
import pandas as pd
import numpy as np

from .models import VolatilityMetrics, TimeframeVolatility
from .utils import get_timeframe_minutes, calculate_percentile
from .indicators import (
    calculate_atr, calculate_bb_width, calculate_volatility_change
)
from .analysis import analyze_volatility_nature, interpret_volatility


class VolatilityCalculator:
    """
    Calculator for volatility metrics across timeframes.
    
    Combines multiple indicators and analysis methods to provide:
    - Volatility level and nature (directional vs chaotic)
    - Market efficiency metrics
    - Risk adjustment recommendations
    - Trading implications
    """

    def __init__(self, historical_window: int = 100):
        self.historical_window = historical_window
        self.period = 14  # Default period for indicators

    def calculate_metrics(self, df: pd.DataFrame, timeframe: str) -> VolatilityMetrics:
        """
        Calculate comprehensive volatility metrics for a single timeframe.
        
        Args:
            df: DataFrame with OHLCV data
            timeframe: Timeframe identifier (e.g. '4H', '1H', '15m')
            
        Returns:
            VolatilityMetrics object containing:
            - Basic volatility measures (ATR, BB width)
            - Historical context (percentiles)
            - Volatility nature analysis
            - Trading implications
        """
        try:
            with logfire.span(f"calculate_metrics_{timeframe}"):
                # 1. Basic ATR calculations
                atr = calculate_atr(df, self.period)
                atr_current = float(atr.iloc[-1])
                atr_percentile = calculate_percentile(atr, self.historical_window)
                
                # 2. Normalized ATR
                price = float(df["close"].iloc[-1])
                normalized_atr = (atr_current / price) * 100
                
                # 3. Bollinger Bands analysis
                bb_width = calculate_bb_width(df)
                bb_width_current = float(bb_width.iloc[-1])
                bb_width_percentile = calculate_percentile(bb_width, self.historical_window)
                
                # 4. Volatility change calculation
                try:
                    minutes_per_period = get_timeframe_minutes(timeframe)
                    periods_24h = int(24 * 60 / minutes_per_period)
                    volatility_change = calculate_volatility_change(atr, periods_24h)
                except Exception as e:
                    logfire.warning(f"Error calculating 24h change, using fallback: {str(e)}")
                    volatility_change = calculate_volatility_change(atr, 4)  # Fallback to 4 periods
                
                # 5. Volatility nature analysis
                vol_nature = analyze_volatility_nature(df, self.period)
                vol_interpretation = interpret_volatility(vol_nature)
                
                # 6. Calculate normalized direction score (-100 to +100)
                direction_score = vol_nature['directional_strength'] * 100
                if df['close'].iloc[-1] < df['close'].iloc[-self.period]:
                    direction_score *= -1
                
                # 7. Calculate opportunity score based on new metrics
                # Opportunity score uses absolute direction strength for calculation
                opportunity_score = (
                    (1 - vol_nature['chaos_ratio']) *          # Lower chaos increases score
                    abs(vol_nature['directional_strength']) *  # Use absolute directional strength
                    (1 - (0.5 * vol_nature['volatility_score']))  # High volatility reduces score less aggressively
                ) * 100  # Convert to 0-100 scale

                # Ensure opportunity score is within bounds
                opportunity_score = float(np.clip(opportunity_score, 0, 100))

                # Log detailed analysis with structured context
                with logfire.span(f"volatility_analysis_{timeframe}") as span:
                    span.set_attributes({
                        "timeframe": timeframe,
                        "atr": atr_current,
                        "atr_percentile": atr_percentile,
                        "normalized_atr": normalized_atr,
                        "volatility_change_24h": volatility_change,
                        "regime": vol_interpretation['volatility_class'],
                        "direction_score": direction_score,
                        "opportunity_score": opportunity_score
                    })

                    # Log volatility context interpretation
                    volatility_context = {
                        "LOW": "Market showing minimal movement, consider widening stop distances",
                        "NORMAL": "Standard risk parameters apply",
                        "HIGH": f"Consider reducing position sizes by {(1 - vol_nature['directional_strength']) * 100:.0f}%",
                        "EXTREME": "High risk conditions, maximum position reduction recommended"
                    }[vol_interpretation['volatility_class']]

                    # Log directional analysis
                    if direction_score > 70:
                        direction_context = "Strong upward movement with clear directional bias"
                    elif direction_score > 30:
                        direction_context = "Moderate upward trend, showing directional consistency"
                    elif direction_score > -30:
                        direction_context = "Neutral/unclear directional bias"
                    elif direction_score > -70:
                        direction_context = "Moderate downward trend, showing directional consistency"
                    else:
                        direction_context = "Strong downward movement with clear directional bias"

                    # Log trading implications
                    if opportunity_score > 70:
                        trading_context = {
                            "opportunity_level": "HIGH OPPORTUNITY",
                            "description": "Strong directional movement with supporting volatility",
                            "position_sizing": f"Up to {vol_nature['directional_strength'] * 100:.0f}% of normal size",
                            "entry_type": "Can consider market orders if momentum confirms"
                        }
                    elif opportunity_score > 50:
                        trading_context = {
                            "opportunity_level": "MODERATE OPPORTUNITY",
                            "description": "Decent setup with acceptable risk",
                            "position_sizing": f"{vol_nature['directional_strength'] * 100:.0f}% of normal size",
                            "entry_type": "Prefer limit orders at key levels"
                        }
                    elif opportunity_score > 30:
                        trading_context = {
                            "opportunity_level": "CAUTIOUS",
                            "description": "Conditions require careful validation",
                            "position_sizing": f"Maximum {vol_nature['directional_strength'] * 100:.0f}% of normal size",
                            "entry_type": "Only limit orders with clear invalidation"
                        }
                    else:
                        trading_context = {
                            "opportunity_level": "DEFENSIVE",
                            "description": "Not ideal for new positions",
                            "position_sizing": "Focus on managing existing positions",
                            "entry_type": "Consider wider stops if holding through volatility"
                        }

                    # Log market efficiency analysis
                    if bb_width_percentile > 80:
                        efficiency_context = "Market showing significant expansion, expect increased volatility"
                    elif bb_width_percentile > 50:
                        efficiency_context = "Normal market expansion, standard trading conditions"
                    else:
                        efficiency_context = "Compressed market conditions, potential for expansion"

                    # Log complete analysis
                    logfire.info(f"Volatility Analysis for {timeframe}",
                               volatility_context=volatility_context,
                               direction_context=direction_context,
                               trading_context=trading_context,
                               efficiency_context=efficiency_context,
                               extras={
                                   "market_metrics": {
                                       "atr_normalized": f"{normalized_atr:.2f}% of price",
                                       "volatility_change": f"{volatility_change:.2f}% over 24h",
                                       "direction_strength": f"{vol_nature['directional_strength']:.2f}",
                                       "chaos_ratio": f"{vol_nature['chaos_ratio']:.2f}",
                                       "bb_width_percentile": bb_width_percentile
                                   },
                                   "risk_parameters": {
                                       "suggested_size_multiplier": vol_nature['directional_strength'],
                                       "volatility_regime": vol_interpretation['volatility_class'],
                                       "directional_class": vol_interpretation['directional_class'],
                                       "trading_implication": vol_interpretation['trading_implication']
                                   }
                               })

                return VolatilityMetrics(
                    atr=atr_current,
                    atr_percentile=atr_percentile,
                    normalized_atr=normalized_atr,
                    bb_width=bb_width_current,
                    bb_width_percentile=bb_width_percentile,
                    volatility_change_24h=volatility_change,
                    regime=vol_interpretation['volatility_class'],
                    direction_score=direction_score,
                    opportunity_score=opportunity_score
                )
                
        except Exception as e:
            logfire.error(f"Error in calculate_metrics: {str(e)}")
            raise

    def calculate_for_timeframes(self, data: Dict[str, pd.DataFrame]) -> TimeframeVolatility:
        """Calculate volatility metrics for multiple timeframes."""
        metrics = {}
        
        first_df = next(iter(data.values()))
        symbol = first_df.index.name or "UNKNOWN"

        for timeframe, df in data.items():
            try:
                metrics[timeframe] = self.calculate_metrics(df, timeframe)
            except Exception as e:
                logfire.error(f"Error calculating metrics for {timeframe}", error=str(e))
                raise ValueError(f"Error calculating metrics for {timeframe}: {str(e)}")

        return TimeframeVolatility(
            symbol=symbol,
            metrics=metrics
        )