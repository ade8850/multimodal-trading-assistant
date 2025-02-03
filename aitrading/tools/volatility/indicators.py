# aitrading/tools/volatility/indicators.py

from typing import Tuple
import pandas as pd
import numpy as np


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


def calculate_adx_components(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate ADX (Average Directional Index) components."""
    # Positive and Negative Directional Movement
    high_diff = df['high'].diff()
    low_diff = df['low'].diff()

    # Initialize pos_dm and neg_dm with zeros as float64
    pos_dm = pd.Series(np.zeros(len(df)), index=df.index, dtype='float64')
    neg_dm = pd.Series(np.zeros(len(df)), index=df.index, dtype='float64')
    
    # Calculate directional movements
    pos_dm_mask = (high_diff > low_diff.abs())
    neg_dm_mask = (low_diff.abs() > high_diff)
    
    # Use loc for assignment to avoid dtype warnings
    pos_dm.loc[pos_dm_mask] = high_diff[pos_dm_mask]
    neg_dm.loc[neg_dm_mask] = low_diff.abs()[neg_dm_mask]

    tr = pd.DataFrame({
        'tr1': df['high'] - df['low'],
        'tr2': abs(df['high'] - df['close'].shift(1)),
        'tr3': abs(df['low'] - df['close'].shift(1))
    }).max(axis=1)

    # Exponential smoothing
    smoothed_tr = tr.ewm(span=period, adjust=False).mean()
    smoothed_pos_dm = pos_dm.ewm(span=period, adjust=False).mean()
    smoothed_neg_dm = neg_dm.ewm(span=period, adjust=False).mean()

    # Calculate +DI and -DI
    pos_di = 100 * smoothed_pos_dm / smoothed_tr
    neg_di = 100 * smoothed_neg_dm / smoothed_tr

    # Calculate ADX
    dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di)
    adx = dx.ewm(span=period, adjust=False).mean()

    return adx, pos_di, neg_di


def calculate_efficiency_ratio(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate the Efficiency Ratio (ER) which measures movement directionality.
    ER = abs(close_price_change) / sum(abs(price_changes))
    
    Higher values indicate more directional movement.
    """
    price_change = abs(df['close'] - df['close'].shift(period))
    path_length = df['close'].diff().abs().rolling(period).sum()
    return price_change / path_length


def calculate_money_flow_ratio(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate the ratio between positive and negative money flows.
    
    Uses typical price and volume to determine if money is flowing in or out.
    Returns ratio > 1 for bullish flow, < 1 for bearish flow.
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']
    
    pos_flow = money_flow.where(typical_price > typical_price.shift(1), 0.0)  # Explicitly set to float
    neg_flow = money_flow.where(typical_price < typical_price.shift(1), 0.0)  # Explicitly set to float
    
    pos_flow_sum = pos_flow.rolling(period).sum()
    neg_flow_sum = neg_flow.rolling(period).sum()
    
    # Avoid division by zero
    neg_flow_sum = neg_flow_sum.replace(0, np.nan)
    ratio = pos_flow_sum / neg_flow_sum
    
    return ratio.fillna(1.0)  # 1.0 represents neutral flow


def calculate_normalized_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate ATR normalized by price (ATR/Price * 100).
    Returns ATR as a percentage of current price.
    """
    atr = calculate_atr(df, period)
    norm_atr = (atr / df['close']) * 100
    return norm_atr


def calculate_volatility_change(atr_series: pd.Series, periods: int) -> float:
    """
    Calculate percentage change in ATR over specified number of periods.
    """
    if len(atr_series) < periods:
        periods = len(atr_series) // 2
    
    current = float(atr_series.iloc[-1])
    previous = float(atr_series.iloc[-periods])
    
    if previous == 0:
        return 0.0
        
    return ((current - previous) / previous) * 100