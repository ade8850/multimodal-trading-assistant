# aitrading/agents/models/validity.py

from typing import List, Literal
from pydantic import BaseModel


class PriceLevel(BaseModel):
    """Price level with direction for invalidation."""
    price: float
    direction: Literal["above", "below"]


class Range24h(BaseModel):
    """24-hour price range."""
    high: float
    low: float


class Rationale(BaseModel):
    """Strategy rationale."""
    trend: str
    key_levels: List[float]
    catalysts: List[str]


class TimeFrame(BaseModel):
    """Strategy validity timeframe."""
    start: str
    expiry: str


class InvalidationConditions(BaseModel):
    """Strategy invalidation conditions."""
    price_levels: List[PriceLevel]


class Validity(BaseModel):
    """Strategy validity conditions."""
    timeframe: TimeFrame
    invalidation_conditions: InvalidationConditions
