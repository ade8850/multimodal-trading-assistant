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
    direction_score: float = Field(
        ...,
        ge=-100,
        le=100,
        description="Direction strength score. Positive for upward, negative for downward. Magnitude indicates strength."
    )
    opportunity_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Trade opportunity score based on volatility/direction alignment. Higher values indicate better opportunities."
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
        
    def get_opportunity_summary(self, primary_timeframe: str) -> Dict[str, float]:
        """Get opportunity summary across timeframes.
        
        Args:
            primary_timeframe: Main decision timeframe (e.g. '1H')
            
        Returns:
            Dict containing:
            - primary_score: Opportunity score on primary timeframe
            - confirmation_score: Average alignment of other timeframes
            - overall_score: Combined opportunity rating
        """
        try:
            # Get primary timeframe metrics
            primary_metrics = self.get_metrics(primary_timeframe)
            primary_score = primary_metrics.opportunity_score
            primary_direction = primary_metrics.direction_score
            
            # Calculate confirmation from other timeframes
            other_scores = []
            for tf, metrics in self.metrics.items():
                if tf != primary_timeframe:
                    # Check directional alignment with primary timeframe
                    direction_alignment = (
                        metrics.direction_score * primary_direction > 0
                    )
                    if direction_alignment:
                        other_scores.append(metrics.opportunity_score)
            
            # Calculate confirmation score (if any other timeframes exist)
            confirmation_score = (
                sum(other_scores) / len(other_scores) if other_scores else 0
            )
            
            # Overall score weights primary timeframe more heavily
            overall_score = (primary_score * 0.7 + confirmation_score * 0.3)
            
            return {
                "primary_score": primary_score,
                "confirmation_score": confirmation_score,
                "overall_score": overall_score
            }
            
        except KeyError:
            raise ValueError(f"Primary timeframe {primary_timeframe} not found in metrics")