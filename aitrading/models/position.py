"""Models for trading positions."""

from typing import Optional
from pydantic import Field

from .time_base import TimeBasedModel

class Position(TimeBasedModel):
    """Current position on the exchange."""
    symbol: str
    side: str  # Buy or Sell
    size: float
    entry_price: float = Field(alias="avgPrice")
    leverage: float
    unrealized_pnl: float = Field(alias="unrealisedPnl")
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None

    @classmethod
    def from_exchange_data(cls, data: dict) -> "Position":
        """Create an instance from exchange API response data."""
        # Extract required fields with proper aliases
        position_data = {
            "symbol": data["symbol"],
            "side": data["side"],
            "size": float(data["size"]),
            "avgPrice": float(data["avgPrice"]),
            "leverage": float(data["leverage"]),
            "unrealisedPnl": float(data["unrealisedPnl"]),
            "take_profit": float(data["takeProfit"]) if data.get("takeProfit") else None,
            "stop_loss": float(data["stopLoss"]) if data.get("stopLoss") else None,
        }
        
        # Use updatedTime for both created_at and updated_at
        if "updatedTime" in data:
            timestamp = int(data["updatedTime"])
            return cls.from_timestamp(timestamp, **position_data)
            
        return cls(**position_data)

    @property
    def value(self) -> float:
        """Calculate current position value."""
        return self.size * self.entry_price

    @property
    def margin_used(self) -> float:
        """Calculate margin used by position."""
        return self.value / self.leverage

    def is_in_profit(self) -> bool:
        """Check if position is currently in profit."""
        return self.unrealized_pnl > 0