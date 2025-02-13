from typing import List
from pydantic import BaseModel, Field


class StrategicContext(BaseModel):
    """Strategic context for order evaluation and management."""
    setup_rationale: str = Field(
        description="Original market setup and key technical conditions"
    )
    market_bias: str = Field(
        description="Overall market bias and trend context"
    )
    key_levels: List[float] = Field(
        description="Critical price levels for this setup"
    )
    catalysts: List[str] = Field(
        description="Market conditions or events supporting this setup"
    )
    invalidation_conditions: List[str] = Field(
        description="Specific market conditions that would invalidate this setup"
    )
