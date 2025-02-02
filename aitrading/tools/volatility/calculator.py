# aitrading/tools/volatility/calculator.py

from typing import Dict, Tuple, List
import pandas as pd
import numpy as np
from .models import VolatilityMetrics, TimeframeVolatility


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    return tr.rolling(window=period).mean()


def calculate_bb_width(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """Calculate Bollinger Band Width ((Upper - Lower) / Middle)."""
    middle = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return (upper - lower) / middle


def calculate_percentile(series: pd.Series, window: int) -> float:
    """Calculate the current value's percentile over a historical window."""
    current_value = series.iloc[-1]
    historical_window = series.iloc[-window:]
    return float(pd.Series(historical_window).rank(pct=True).iloc[-1] * 100)


def calculate_directional_strength(df: pd.DataFrame, lookback: int = 20) -> float:
    """Calculate the directional strength of price movement.
    
    Args:
        df: DataFrame with OHLC and indicators
        lookback: Number of periods to analyze
    
    Returns:
        Directional strength score (-100 to +100)
        Positive values indicate upward direction
        Negative values indicate downward direction
        Magnitude indicates strength
    """
    # Get recent data
    recent = df.tail(lookback)

    if 'EMA100' not in df.columns:
        df['EMA100'] = df['close'].ewm(span=100, adjust=False).mean()
    
    # Calculate directional components
    price_direction = (recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0] * 100
    ema_direction = (recent['EMA100'].iloc[-1] - recent['EMA100'].iloc[0]) / recent['EMA100'].iloc[0] * 100
    
    # Calculate BB position score
    bb_middle = recent['close'].rolling(20).mean()
    bb_std = recent['close'].rolling(20).std()
    bb_upper = bb_middle + (2 * bb_std)
    bb_lower = bb_middle - (2 * bb_std)
    
    # Position relative to BB (0 at middle, +/-1 at bands)
    bb_position = ((recent['close'] - bb_middle) / (bb_upper - bb_lower)).mean()
    
    # Volume-price correlation
    volume_direction = np.where(recent['close'] > recent['close'].shift(1), recent['volume'], -recent['volume'])
    volume_price_correlation = pd.Series(volume_direction).corr(recent['close'])
    
    # Combine components
    direction_score = (
        price_direction * 0.4 +      # Price trend
        ema_direction * 0.3 +        # EMA trend
        bb_position * 20 +           # BB position
        volume_price_correlation * 10 # Volume confirmation
    )
    
    # Bound the score
    return np.clip(direction_score, -100, 100)


def get_timeframe_minutes(timeframe: str) -> int:
    """Get number of minutes for a timeframe."""
    timeframe = timeframe.upper()
    if timeframe.endswith('M'):
        return int(timeframe[:-1])
    elif timeframe.endswith('H'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('D'):
        return int(timeframe[:-1]) * 1440
    raise ValueError(f"Unsupported timeframe format: {timeframe}")


def analyze_volatility_context(
    atr_percentile: float,
    bb_width_percentile: float,
    direction_score: float,
    vol_change_24h: float
) -> Tuple[str, float]:
    """Analyze volatility context considering direction.
    
    Args:
        atr_percentile: Historical percentile of current ATR
        bb_width_percentile: Historical percentile of current BB width
        direction_score: Directional strength score (-100 to +100)
        vol_change_24h: 24h change in volatility
    
    Returns:
        Tuple of (regime, opportunity_score)
        regime: Volatility classification (LOW/MEDIUM/HIGH/EXTREME)
        opportunity_score: Score indicating trade opportunity (0-100)
    """
    # Base volatility score
    vol_score = (atr_percentile * 0.4 +    # ATR has significant weight
                bb_width_percentile * 0.4 + # BB width equally important
                min(abs(vol_change_24h) * 2, 100) * 0.2)  # Recent change
    
    # Direction alignment
    direction_alignment = abs(direction_score) / 100  # 0 to 1
    
    # Opportunity score increases when:
    # - High volatility aligns with strong direction
    # - Low volatility with weak direction gets low score
    opportunity_score = vol_score * direction_alignment
    
    # Regime classification
    if vol_score < 30:
        regime = "LOW"
    elif vol_score < 60:
        regime = "MEDIUM"
    elif vol_score < 85:
        regime = "HIGH"
    else:
        regime = "EXTREME"
    
    return regime, min(opportunity_score, 100)


class VolatilityCalculator:
    """Calculator for volatility metrics across timeframes."""

    def __init__(self, historical_window: int = 100):
        self.historical_window = historical_window
        
    def calculate_metrics(self, df: pd.DataFrame, timeframe: str) -> VolatilityMetrics:
        """Calculate volatility metrics for a single timeframe."""
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
            minutes_per_period = get_timeframe_minutes(timeframe)
            periods_24h = int(24 * 60 / minutes_per_period)
            if periods_24h >= len(atr):
                periods_24h = len(atr) // 2
            atr_24h_ago = float(atr.iloc[-periods_24h])
            volatility_change = ((atr_current - atr_24h_ago) / atr_24h_ago) * 100
        except Exception as e:
            periods_24h = 4
            atr_24h_ago = float(atr.iloc[-periods_24h])
            volatility_change = ((atr_current - atr_24h_ago) / atr_24h_ago) * 100
        
        # Calculate directional strength
        direction_score = calculate_directional_strength(df)
        
        # Analyze volatility context
        regime, opportunity_score = analyze_volatility_context(
            atr_percentile,
            bb_width_percentile,
            direction_score,
            volatility_change
        )
        
        return VolatilityMetrics(
            atr=atr_current,
            atr_percentile=atr_percentile,
            normalized_atr=normalized_atr,
            bb_width=bb_width_current,
            bb_width_percentile=bb_width_percentile,
            volatility_change_24h=volatility_change,
            regime=regime,
            direction_score=direction_score,
            opportunity_score=opportunity_score
        )
        
    def calculate_for_timeframes(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> TimeframeVolatility:
        """Calculate volatility metrics for multiple timeframes."""
        metrics = {}
        
        first_df = next(iter(data.values()))
        symbol = first_df.index.name or "UNKNOWN"
        
        for timeframe, df in data.items():
            try:
                metrics[timeframe] = self.calculate_metrics(df, timeframe)
            except Exception as e:
                raise ValueError(f"Error calculating metrics for {timeframe}: {str(e)}")
                
        return TimeframeVolatility(
            symbol=symbol,
            metrics=metrics
        )