# aitrading/tools/volatility/models.py

from typing import Dict, Literal
from pydantic import BaseModel, Field


class VolatilityMetrics(BaseModel):
    """Volatility metrics for a single timeframe."""
    atr: float = Field(..., description="Current ATR value")
    atr_percentile: float = Field(
        ...,
        ge=0,
        le=100,
        description="Historical percentile of current ATR"
    )
    normalized_atr: float = Field(
        ...,
        description="ATR as percentage of price (ATR/Price * 100)"
    )
    bb_width: float = Field(
        ...,
        description="Current Bollinger Band width ((Upper-Lower)/Middle)"
    )
    bb_width_percentile: float = Field(
        ...,
        ge=0,
        le=100,
        description="Historical percentile of current BB width"
    )
    volatility_change_24h: float = Field(
        ...,
        description="Percentage change in ATR over last 24h"
    )
    regime: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"] = Field(
        ...,
        description="Current volatility regime classification"
    )


class TimeframeVolatility(BaseModel):
    """Volatility metrics for each analyzed timeframe."""
    symbol: str = Field(..., description="Trading pair symbol")
    metrics: Dict[str, VolatilityMetrics] = Field(
        ...,
        description="Volatility metrics by timeframe (e.g. '4H', '1H', '15m')"
    )

    def get_metrics(self, timeframe: str) -> VolatilityMetrics:
        """Get metrics for a specific timeframe.
        
        Args:
            timeframe: Timeframe identifier (e.g. '4H', '1H', '15m')
            
        Returns:
            VolatilityMetrics for the specified timeframe
            
        Raises:
            KeyError: If timeframe not found
        """
        if timeframe not in self.metrics:
            raise KeyError(f"No metrics available for timeframe: {timeframe}")
        return self.metrics[timeframe]