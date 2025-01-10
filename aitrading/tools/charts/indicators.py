# aitrading/tools/charts/indicators.py

import pandas as pd


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators."""
    df = df.copy()

    # EMAs
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI
    df["RSI"] = _calculate_rsi(df)

    # MACD
    df = _calculate_macd(df)

    # Bollinger Bands
    df = _calculate_bollinger_bands(df)

    return df


def _calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate RSI indicator."""
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MACD indicator."""
    exp1 = df["close"].ewm(span=12, adjust=False).mean()
    exp2 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df


def _calculate_bollinger_bands(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Calculate Bollinger Bands."""
    middle_band = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    df["BB_upper"] = middle_band + (2 * std)
    df["BB_middle"] = middle_band
    df["BB_lower"] = middle_band - (2 * std)
    return df
