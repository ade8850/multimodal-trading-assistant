# aitrading/agents/models/orders.py

from typing import Optional, Literal
from pydantic import BaseModel, Field, validator

class OrderExitLevel(BaseModel):
    """Single exit level with price and size."""
    price: float
    size_percentage: float

class OrderExit(BaseModel):
    """Exit conditions including take profit and stop loss."""
    take_profit: OrderExitLevel
    stop_loss: OrderExitLevel

class OrderEntry(BaseModel):
    """Entry order details."""
    price: Optional[float] = None
    budget: float
    leverage: int

class Order(BaseModel):
    """Complete order specification."""
    type: Literal["market", "limit"]
    entry: OrderEntry
    exit: OrderExit

class ExistingOrder(BaseModel):
    """Representation of an existing order on the exchange."""
    id: str  # Exchange-assigned order ID
    order_link_id: str  # Custom order link ID
    symbol: str
    type: str
    side: str
    price: Optional[float]
    qty: float
    created_time: str
    updated_time: str
    status: str
    take_profit: Optional[float]
    stop_loss: Optional[float]

class OrderCancellation(BaseModel):
    """Specification for an order to be cancelled."""
    id: str = Field(
        description="Exchange-assigned order ID from the active orders list"
    )
    order_link_id: Optional[str] = Field(
        None,
        description="Optional custom order link ID from the active orders list"
    )
    symbol: str = Field(
        description="Trading pair symbol (e.g. BTCUSDT)"
    )
    reason: str = Field(
        description="Explanation of why this order should be cancelled"
    )

    @validator('id')
    def validate_id(cls, v):
        """Ensure ID is not None or empty."""
        if not v:
            raise ValueError("Exchange order ID is required for cancellation")
        return v

    @validator('symbol')
    def validate_symbol(cls, v):
        """Ensure symbol is not None or empty."""
        if not v:
            raise ValueError("Trading symbol is required for cancellation")
        return v