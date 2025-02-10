# aitrading/models/orders.py

from typing import Optional, Literal, List
from pydantic import BaseModel, Field, validator
from enum import Enum

from .time_base import TimeBasedModel


class OrderRole(str, Enum):
    """Role of the order in the trading strategy."""
    ENTRY = "entry"  # Main entry order
    PROTECT = "protect"  # Protection order (stop loss)
    PROFIT = "profit"  # Take profit order
    EXIT = "exit"  # Generic exit order


class OrderEntry(BaseModel):
    """Entry order details."""
    price: Optional[float] = None
    budget: float
    leverage: int


class OrderParameters(BaseModel):
    """Common parameters for all order types."""
    symbol: str
    type: Literal["market", "limit"]
    side: Literal["Buy", "Sell"]
    size: float
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    reduce_only: bool = False
    close_on_trigger: bool = False
    position_idx: int = 0


class ChildOrder(BaseModel):
    """Definition of a child order (TP/SL) related to a parent order."""
    role: OrderRole
    parameters: OrderParameters
    parent_order_id: Optional[str] = None
    parent_link_id: Optional[str] = None


class Order(BaseModel):
    """Complete order specification."""
    type: Literal["market", "limit"]
    entry: OrderEntry
    child_orders: List[ChildOrder] = Field(
        default_factory=list,
        description="List of child orders (TP/SL) associated with this order"
    )


class ExistingOrder(TimeBasedModel):
    """Representation of an existing order on the exchange."""
    id: str  # Exchange-assigned order ID
    order_link_id: str  # Custom order link ID
    symbol: str
    type: str
    side: str
    price: Optional[float]
    qty: float
    status: str
    take_profit: Optional[float]
    stop_loss: Optional[float]
    role: Optional[OrderRole] = Field(
        None,
        description="Role of the order in the strategy"
    )
    parent_order_id: Optional[str] = Field(
        None,
        description="ID of parent order if this is a child order"
    )
    reduce_only: bool = False

    @classmethod
    def from_exchange_data(cls, data: dict) -> "ExistingOrder":
        """Create an instance from exchange API response data."""
        # Extract required fields
        order_data = {
            "id": data["orderId"],
            "order_link_id": data.get("orderLinkId", ""),
            "symbol": data["symbol"],
            "type": data["orderType"],
            "side": data["side"],
            "price": float(data["price"]) if data["price"] != "0" else None,
            "qty": float(data["qty"]),
            "status": data["orderStatus"],
            "take_profit": float(data["takeProfit"]) if data.get("takeProfit") else None,
            "stop_loss": float(data["stopLoss"]) if data.get("stopLoss") else None,
            "reduce_only": data.get("reduceOnly", False),
        }

        # Use updatedTime for both created_at and updated_at
        if "updatedTime" in data:
            timestamp = int(data["updatedTime"])
            return cls.from_timestamp(timestamp, **order_data)

        return cls(**order_data)


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