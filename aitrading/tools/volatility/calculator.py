# aitrading/tools/volatility/calculator.py

from typing import Dict, Tuple, List
import pandas as pd
import numpy as np
from .models import VolatilityMetrics, TimeframeVolatility


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range.
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period
    
    Returns:
        Series with ATR values
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    tr1 = high - low  # Current high - current low
    tr2 = abs(high - close.shift())  # Current high - previous close
    tr3 = abs(low - close.shift())  # Current low - previous close
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    return tr.rolling(window=period).mean()


def calculate_bb_width(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """Calculate Bollinger Band Width ((Upper - Lower) / Middle).
    
    Args:
        df: DataFrame with OHLC data
        period: MA period for BB calculation
        std_dev: Number of standard deviations
    
    Returns:
        Series with BB Width values
    """
    middle = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return (upper - lower) / middle


def calculate_percentile(series: pd.Series, window: int) -> float:
    """Calculate the current value's percentile over a historical window.
    
    Args:
        series: Time series data
        window: Historical window for percentile calculation
    
    Returns:
        Current value's percentile (0-100)
    """
    current_value = series.iloc[-1]
    historical_window = series.iloc[-window:]
    return float(pd.Series(historical_window).rank(pct=True).iloc[-1] * 100)


def get_timeframe_minutes(timeframe: str) -> int:
    """Get number of minutes for a timeframe.
    
    Args:
        timeframe: String representing timeframe (e.g., '5m', '1H', '4H')
        
    Returns:
        Number of minutes
    """
    timeframe = timeframe.upper()
    if timeframe.endswith('M'):
        return int(timeframe[:-1])
    elif timeframe.endswith('H'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('D'):
        return int(timeframe[:-1]) * 1440
    raise ValueError(f"Unsupported timeframe format: {timeframe}")


def classify_volatility(
    atr_percentile: float,
    bb_width_percentile: float,
    vol_change_24h: float
) -> str:
    """Classify volatility regime based on multiple metrics.
    
    Args:
        atr_percentile: Historical percentile of current ATR
        bb_width_percentile: Historical percentile of current BB width
        vol_change_24h: 24h change in volatility
    
    Returns:
        Volatility regime classification (LOW/MEDIUM/HIGH/EXTREME)
    """
    # Combined score between 0-100
    score = (atr_percentile * 0.4 +  # ATR has highest weight
            bb_width_percentile * 0.4 +  # BB width equally important
            min(abs(vol_change_24h) * 2, 100) * 0.2)  # Recent change has lower weight
    
    if score < 30:
        return "LOW"
    elif score < 60:
        return "MEDIUM"
    elif score < 85:
        return "HIGH"
    else:
        return "EXTREME"


class VolatilityCalculator:
    """Calculator for volatility metrics across timeframes."""

    def __init__(self, historical_window: int = 100):
        """Initialize calculator.
        
        Args:
            historical_window: Number of periods for percentile calculations
        """
        self.historical_window = historical_window
        
    def calculate_metrics(self, df: pd.DataFrame, timeframe: str) -> VolatilityMetrics:
        """Calculate volatility metrics for a single timeframe.
        
        Args:
            df: DataFrame with OHLC data
            timeframe: String representing timeframe (e.g., '5m', '1H', '4H')
        
        Returns:
            VolatilityMetrics object with calculated values
        """
        # Calculate ATR and related metrics
        atr = calculate_atr(df)
        atr_current = float(atr.iloc[-1])
        atr_percentile = calculate_percentile(atr, self.historical_window)
        
        # Calculate normalized ATR
        price = float(df["close"].iloc[-1])
        normalized_atr = (atr_current / price) * 100
        
        # Calculate BB width and percentile
        bb_width = calculate_bb_width(df)
        bb_width_current = float(bb_width.iloc[-1])
        bb_width_percentile = calculate_percentile(bb_width, self.historical_window)
        
        # Calculate 24h volatility change
        try:
            # Calculate periods based on timeframe string
            minutes_per_period = get_timeframe_minutes(timeframe)
            periods_24h = int(24 * 60 / minutes_per_period)
            if periods_24h >= len(atr):
                periods_24h = len(atr) // 2  # Use half the available data if not enough history
            atr_24h_ago = float(atr.iloc[-periods_24h])
            volatility_change = ((atr_current - atr_24h_ago) / atr_24h_ago) * 100
        except Exception as e:
            # If there's any error in 24h calculation, use a minimal lookback
            periods_24h = 4  # Minimal lookback
            atr_24h_ago = float(atr.iloc[-periods_24h])
            volatility_change = ((atr_current - atr_24h_ago) / atr_24h_ago) * 100
        
        # Classify volatility regime
        regime = classify_volatility(atr_percentile, bb_width_percentile, volatility_change)
        
        return VolatilityMetrics(
            atr=atr_current,
            atr_percentile=atr_percentile,
            normalized_atr=normalized_atr,
            bb_width=bb_width_current,
            bb_width_percentile=bb_width_percentile,
            volatility_change_24h=volatility_change,
            regime=regime
        )
        
    def calculate_for_timeframes(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> TimeframeVolatility:
        """Calculate volatility metrics for multiple timeframes.
        
        Args:
            data: Dictionary mapping timeframe names to DataFrames
        
        Returns:
            TimeframeVolatility object with metrics for all timeframes
        """
        metrics = {}
        
        # Extract symbol from first dataframe (should be same for all)
        first_df = next(iter(data.values()))
        symbol = first_df.index.name or "UNKNOWN"
        
        # Calculate metrics for each timeframe
        for timeframe, df in data.items():
            try:
                metrics[timeframe] = self.calculate_metrics(df, timeframe)
            except Exception as e:
                raise ValueError(f"Error calculating metrics for {timeframe}: {str(e)}")
                
        return TimeframeVolatility(
            symbol=symbol,
            metrics=metrics
        )