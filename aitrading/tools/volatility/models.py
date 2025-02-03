# aitrading/tools/volatility/models.py

from typing import Dict, Literal
from pydantic import BaseModel, Field

VolatilityClass = Literal["LOW", "NORMAL", "HIGH", "EXTREME"]
DirectionalClass = Literal["STRONGLY_DIRECTIONAL", "MODERATELY_DIRECTIONAL", "WEAKLY_DIRECTIONAL", "CHAOTIC"]
TradingImplication = Literal["OPPORTUNITY", "CAUTIOUS_OPPORTUNITY", "NEUTRAL", "RISK"]

class VolatilityNature(BaseModel):
    """Detailed analysis of volatility nature."""
    volatility_class: VolatilityClass = Field(
        ...,
        description="Classification based on absolute volatility level"
    )
    directional_class: DirectionalClass = Field(
        ...,
        description="Classification of directional strength"
    )
    trading_implication: TradingImplication = Field(
        ...,
        description="Trading implication based on volatility analysis"
    )
    directional_strength: float = Field(
        ...,
        ge=0,
        le=1,
        description="Normalized measure of price movement efficiency (0-1)"
    )
    chaos_ratio: float = Field(
        ...,
        ge=0,
        le=1,
        description="Proportion of volatility that is non-directional (0-1)"
    )


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
    regime: VolatilityClass = Field(
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
        description="Trade opportunity score considering volatility nature and directionality"
    )
    risk_adjustment: float = Field(
        default=1.0,
        ge=0.2,
        le=1.0,
        description="Position sizing multiplier based on volatility characteristics"
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
        
        This method provides a comprehensive analysis by:
        1. Evaluating primary timeframe metrics
        2. Checking alignment with other timeframes
        3. Weighing opportunities based on volatility nature
        
        Args:
            primary_timeframe: Main decision timeframe (e.g. '1H')
            
        Returns:
            Dict containing:
            - primary_score: Opportunity score on primary timeframe
            - risk_adjusted_score: Score adjusted for volatility risk
            - confirmation_score: Average alignment of other timeframes
            - overall_score: Final weighted opportunity rating
            - position_sizing: Recommended position size multiplier
        """
        try:
            # Get primary timeframe metrics
            primary_metrics = self.get_metrics(primary_timeframe)
            primary_score = primary_metrics.opportunity_score
            primary_direction = primary_metrics.direction_score
            
            # Track directional alignment scores
            aligned_scores = []
            for tf, metrics in self.metrics.items():
                if tf != primary_timeframe:
                    # Check both directional alignment and volatility regime compatibility
                    direction_alignment = metrics.direction_score * primary_direction > 0
                    regime_compatible = metrics.regime in ["NORMAL", "HIGH"]
                    
                    if direction_alignment and regime_compatible:
                        # Weight the score based on volatility regime
                        regime_weight = {
                            "LOW": 0.7,
                            "NORMAL": 1.0,
                            "HIGH": 0.8,
                            "EXTREME": 0.5
                        }[metrics.regime]
                        
                        adjusted_score = metrics.opportunity_score * regime_weight
                        aligned_scores.append(adjusted_score)
            
            # Calculate confirmation score
            confirmation_score = (
                sum(aligned_scores) / len(aligned_scores) if aligned_scores else 0
            )
            
            # Calculate risk-adjusted primary score
            risk_adjusted_score = primary_score * primary_metrics.risk_adjustment
            
            # Calculate final weighted score
            overall_score = (
                risk_adjusted_score * 0.6 +  # Primary timeframe
                confirmation_score * 0.4     # Confirmation from other timeframes
            )
            
            return {
                "primary_score": primary_score,
                "risk_adjusted_score": risk_adjusted_score,
                "confirmation_score": confirmation_score,
                "overall_score": overall_score,
                "position_sizing": primary_metrics.risk_adjustment
            }
            
        except KeyError:
            raise ValueError(f"Primary timeframe {primary_timeframe} not found in metrics")