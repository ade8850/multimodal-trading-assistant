# aitrading/tools/charts/indicators.py

from typing import Dict, Any
import pandas as pd
from .models import (
    EmaParameters, BollingerParameters, RsiParameters,
    MacdParameters, VolumeParameters, IndicatorConfig
)

class IndicatorCalculator:
    """Class for calculating technical indicators with configurable parameters."""
    
    def __init__(self, df: pd.DataFrame):
        """Initialize with a DataFrame containing OHLCV data."""
        self.df = df.copy()
        
    def calculate_ema(self, params: EmaParameters) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return self.df["close"].ewm(span=params.period, adjust=False).mean()
        
    def calculate_bollinger(self, params: BollingerParameters) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands."""
        middle_band = self.df["close"].rolling(window=params.period).mean()
        std = self.df["close"].rolling(window=params.period).std()
        
        return {
            "BB_upper": middle_band + (params.std_dev * std),
            "BB_middle": middle_band,
            "BB_lower": middle_band - (params.std_dev * std)
        }
        
    def calculate_rsi(self, params: RsiParameters) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = self.df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=params.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=params.period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    def calculate_macd(self, params: MacdParameters) -> Dict[str, pd.Series]:
        """Calculate MACD indicator."""
        exp1 = self.df["close"].ewm(span=params.fast_period, adjust=False).mean()
        exp2 = self.df["close"].ewm(span=params.slow_period, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=params.signal_period, adjust=False).mean()
        
        return {
            "MACD": macd,
            "MACD_signal": signal,
            "MACD_hist": macd - signal
        }
        
    def calculate_volume(self, params: VolumeParameters) -> Dict[str, pd.Series]:
        """Calculate Volume and optionally Volume MA."""
        result = {"volume": self.df["volume"]}
        
        if params.ma_period:
            result["volume_ma"] = self.df["volume"].rolling(
                window=params.ma_period).mean()
            
        return result

    def calculate_indicator(self, config: IndicatorConfig) -> Dict[str, pd.Series]:
        """Calculate a single indicator based on its configuration."""
        if config.type == "ema":
            # Usa il periodo nel nome della colonna
            period = config.parameters.period
            return {f"EMA{period}": self.calculate_ema(config.parameters)}
        elif config.type == "bollinger":
            return self.calculate_bollinger(config.parameters)
        elif config.type == "rsi":
            return {"RSI": self.calculate_rsi(config.parameters)}
        elif config.type == "macd":
            return self.calculate_macd(config.parameters)
        elif config.type == "volume":
            return self.calculate_volume(config.parameters)
        else:
            raise ValueError(f"Unsupported indicator type: {config.type}")

    def calculate_all(self, configs: list[IndicatorConfig]) -> pd.DataFrame:
        """Calculate all configured indicators."""
        df_result = self.df.copy()
        
        for config in configs:
            indicator_data = self.calculate_indicator(config)
            for name, series in indicator_data.items():
                df_result[name] = series
                
        return df_result


# Legacy functions for backward compatibility
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Legacy function that calculates all indicators with default parameters."""
    from .models import ChartConfig
    
    # Create default configuration for backward compatibility
    config = ChartConfig.get_default_config("LEGACY", ["CURRENT"])
    timeframe_config = config.timeframes[0]
    
    calculator = IndicatorCalculator(df)
    return calculator.calculate_all(timeframe_config.indicators)

def _calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Legacy RSI calculation function."""
    calculator = IndicatorCalculator(df)
    params = RsiParameters(period=period)
    return calculator.calculate_rsi(params)

def _calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Legacy MACD calculation function."""
    calculator = IndicatorCalculator(df)
    params = MacdParameters()  # Use default parameters
    df = df.copy()
    df.update(calculator.calculate_macd(params))
    return df

def _calculate_bollinger_bands(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Legacy Bollinger Bands calculation function."""
    calculator = IndicatorCalculator(df)
    params = BollingerParameters(period=period)
    df = df.copy()
    df.update(calculator.calculate_bollinger(params))
    return df