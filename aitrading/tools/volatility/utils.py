# aitrading/tools/volatility/utils.py

import pandas as pd

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


def get_dynamic_lookback(timeframe: str) -> int:
    """
    Returns appropriate lookback for the timeframe maintaining consistent time window.
    Based on ~16h of trading to account for gaps.
    """
    minutes_target = 16 * 60  # 960 minutes
    tf_minutes = get_timeframe_minutes(timeframe)
    periods = minutes_target // tf_minutes

    # Minimum 10 periods for statistical significance
    return max(10, periods)


def calculate_percentile(series: pd.Series, window: int) -> float:
    """Calculate the current value's percentile over a historical window."""
    current_value = series.iloc[-1]
    historical_window = series.iloc[-window:]
    return float(pd.Series(historical_window).rank(pct=True).iloc[-1] * 100)