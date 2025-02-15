# aitrading/models/orders.py
from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, validator
import time
import logfire

from .strategy import StrategicContext
from .time_base import TimeBasedModel

class OrderExecutionType(str, Enum):
    """Specifies how the order should be executed."""
    IMMEDIATE = "immediate"    # Execute immediately at market
    PASSIVE = "passive"        # Wait for price to reach level
    TRIGGER = "trigger"        # Execute when condition met


class RiskLevel(str, Enum):
    """Risk level for the order."""
    CRITICAL = "critical"      # Must execute quickly
    NORMAL = "normal"         # Standard execution
    MINIMAL = "minimal"       # Can wait for better price


class OrderEntry(BaseModel):
    """Entry order details."""
    price: Optional[float] = None
    budget: float
    leverage: int
    size_percentage: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Percentage of position to close, only for reduce-only orders"
    )


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


class Order(BaseModel):
    """Complete order specification."""
    type: Literal["market", "limit"]
    entry: OrderEntry


class Range24h(BaseModel):
    """24-hour price range."""
    high: float
    low: float


class PlannedOrder(BaseModel):
    """Complete planned order specification."""
    id: int = Field(default=0, description="Progressive number starting from 1")
    type: Literal["long", "short"]
    symbol: str
    current_price: float
    range_24h: Range24h
    order: Order
    strategic_context: StrategicContext = Field(
        ...,
        description="Strategic context for evaluating order validity"
    )
    order_link_id: Optional[str] = Field(
        None,
        description="Must be in format '{plan_id}-{session_id}-{order_number}-{timestamp}'"
    )
    execution_type: OrderExecutionType = Field(
        default=OrderExecutionType.PASSIVE,
        description="How the order should be executed"
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.NORMAL,
        description="Risk level affecting execution priority"
    )
    reduce_only: bool = Field(
        default=False,
        description="If True, this order can only reduce an existing position"
    )

    def set_order_link_id(self, plan_id: str, session_id: str, order_num: int) -> None:
        """Set the order_link_id using plan_id, session_id, order number and timestamp.

        Args:
            plan_id: Unique plan identifier
            session_id: Session identifier
            order_num: Progressive order number

        The order_link_id will be in format: {plan_id}-{session_id}-{order_num}-{timestamp}
        where timestamp is in milliseconds to ensure global uniqueness.
        """
        if not self.order_link_id:
            timestamp = int(time.time() * 1000)  # millisecondi per unicità
            self.order_link_id = f"{plan_id}-{session_id}-{order_num}-{timestamp}"
            logfire.info("Generated order link id",
                         order_link_id=self.order_link_id,
                         plan_id=plan_id,
                         session_id=session_id,
                         order_num=order_num,
                         timestamp=timestamp)
            self.id = order_num

    @validator('reduce_only')
    def validate_reduce_only(cls, v, values):
        """Validate reduce-only orders."""
        if not v:
            return v

        if not all(field in values for field in ['type', 'symbol']):
            raise ValueError("Reduce-only orders must have type and symbol specified")

        if 'order' not in values:
            raise ValueError("Reduce-only orders must have order details")

        # Validate size_percentage if present
        entry = values['order'].entry
        if hasattr(entry, 'size_percentage') and entry.size_percentage is not None:
            if entry.size_percentage <= 0 or entry.size_percentage > 100:
                raise ValueError("Size percentage must be between 0 and 100")

        return v


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
    reduce_only: bool = False
    strategic_context: Optional[StrategicContext] = Field(
        None,
        description="Strategic context and rationale for this order"
    )

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