from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field, model_validator


class BaseIndicatorParameters(BaseModel):
    """Base class for all indicator parameters."""
    pass


class EmaParameters(BaseIndicatorParameters):
    """Parameters for Exponential Moving Average."""
    period: int = Field(
        default=20,
        ge=1,
        description="Number of periods for EMA calculation"
    )


class BollingerParameters(BaseIndicatorParameters):
    """Parameters for Bollinger Bands."""
    period: int = Field(
        default=20,
        ge=1,
        description="Number of periods for moving average"
    )
    std_dev: float = Field(
        default=2.0,
        ge=0,
        description="Number of standard deviations"
    )
    calculate_width: bool = Field(
        default=False,
        description="Calculate Bollinger Bandwidth"
    )
    store_percentile: bool = Field(
        default=False,
        description="Store historical percentile of bandwidth"
    )


class RsiParameters(BaseIndicatorParameters):
    """Parameters for Relative Strength Index."""
    period: int = Field(
        default=14,
        ge=1,
        description="Number of periods for RSI calculation"
    )
    overbought: float = Field(
        default=70.0,
        ge=0,
        le=100,
        description="Overbought level"
    )
    oversold: float = Field(
        default=30.0,
        ge=0,
        le=100,
        description="Oversold level"
    )


class MacdParameters(BaseIndicatorParameters):
    """Parameters for Moving Average Convergence Divergence."""
    fast_period: int = Field(
        default=12,
        ge=1,
        description="Fast EMA period"
    )
    slow_period: int = Field(
        default=26,
        ge=1,
        description="Slow EMA period"
    )
    signal_period: int = Field(
        default=9,
        ge=1,
        description="Signal line period"
    )

    @model_validator(mode='after')
    def validate_periods(self):
        """Validate that fast period is less than slow period."""
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")
        return self


class VolumeParameters(BaseIndicatorParameters):
    """Parameters for Volume indicator."""
    ma_period: Optional[int] = Field(
        default=20,
        ge=1,
        description="Period for volume moving average"
    )


class AtrParameters(BaseIndicatorParameters):
    """Parameters for Average True Range."""
    period: int = Field(
        default=14,
        ge=1,
        description="Number of periods for ATR calculation"
    )
    store_percentile: bool = Field(
        default=False,
        description="Store historical percentile of ATR"
    )
    normalize: bool = Field(
        default=False,
        description="Calculate normalized ATR (ATR/Close Price)"
    )


# Mapping between indicator type and its parameter class
INDICATOR_PARAMS_MAP = {
    "ema": EmaParameters,
    "bollinger": BollingerParameters,
    "rsi": RsiParameters,
    "macd": MacdParameters,
    "volume": VolumeParameters,
    "atr": AtrParameters
}


class IndicatorConfig(BaseModel):
    """Configuration for a single indicator."""
    type: str
    parameters: Union[EmaParameters, BollingerParameters, RsiParameters,
                     MacdParameters, VolumeParameters, AtrParameters]
    subplot: bool = False
    overlay: bool = False

    @model_validator(mode='before')
    @classmethod
    def validate_parameters_type(cls, values):
        """Validate that parameters match the indicator type."""
        indicator_type = values.get('type')
        parameters = values.get('parameters', {})
        
        if indicator_type not in INDICATOR_PARAMS_MAP:
            raise ValueError(f"Unsupported indicator type: {indicator_type}")
            
        # If parameters is already the correct instance, return it
        if isinstance(parameters, BaseIndicatorParameters):
            param_class = parameters.__class__
            if param_class != INDICATOR_PARAMS_MAP[indicator_type]:
                raise ValueError(
                    f"Parameters type mismatch. Expected {INDICATOR_PARAMS_MAP[indicator_type]}, "
                    f"got {param_class}"
                )
            return values
            
        # Otherwise create the correct instance
        param_class = INDICATOR_PARAMS_MAP[indicator_type]
        values['parameters'] = param_class(**(parameters or {}))
        return values


class ChartView(BaseModel):
    """Configuration for a single chart view."""
    name: str
    title: str
    height_ratio: float = Field(
        default=1.0,
        gt=0,
        description="Relative height of this view compared to others"
    )
    indicators: List[IndicatorConfig]


class TimeframeConfig(BaseModel):
    """Configuration for a single timeframe."""
    timeframe: str
    interval: str
    candles: int = Field(ge=1, description="Number of candles to fetch")
    minutes: int = Field(ge=1, description="Minutes per candle")
    views: List[ChartView]


class ChartConfig(BaseModel):
    """Complete configuration for chart generation."""
    symbol: str
    timeframes: List[TimeframeConfig]