# aitrading/agents/models/trading.py

from typing import List, Optional, Dict, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from .base import generate_uuid_short
from .orders import Order, OrderCancellation
from .validity import Validity, Range24h, Rationale

class PlannedOrder(BaseModel):
    """Complete planned order specification."""
    id: int = Field(default=0, description="Progressive number starting from 1")
    type: Literal["long", "short"]
    symbol: str
    current_price: float
    range_24h: Range24h
    rationale: Rationale
    order: Order
    validity: Validity
    order_link_id: Optional[str] = Field(
        None,
        description="Must be in format '{plan_id}-{session_id}-{order_number}' using the provided plan_id and session_id"
    )

    def set_order_link_id(self, plan_id: str, session_id: str, order_num: int) -> None:
        """Set the order_link_id using plan_id, session_id and order number and update id."""
        if not self.order_link_id:
            self.order_link_id = f"{plan_id}-{session_id}-{order_num}"
            self.id = order_num

class PositionUpdate(BaseModel):
    """Specification for updating an existing position's TP/SL."""
    symbol: str = Field(..., description="Trading pair symbol")
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    reason: str = Field(..., description="Explanation for the modification")

class TradingParameters(BaseModel):
    """Input parameters for the trading plan."""
    symbol: str
    budget: float = Field(ge=10)
    leverage: int = Field(ge=1, le=100)
    timeframe: Literal["Short (1-7d)", "Medium (1-4w)", "Long (1-6m)"]
    risk_level: Literal["Low", "Medium", "High"]
    strategy_instructions: str = Field(
        default="Find the most appropriate entry point based on market conditions."
    )

class TradingPlan(BaseModel):
    """Complete trading plan including parameters and planned orders."""
    id: str = Field(
        default_factory=lambda: generate_uuid_short(8),
        description="An eight-character random string"
    )
    session_id: str = Field(
        default_factory=lambda: generate_uuid_short(4),
        description="A four-character session identifier"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parameters: TradingParameters
    cancellations: Optional[List[OrderCancellation]] = Field(
        default=None,
        description="List of orders to be cancelled before executing new orders"
    )
    orders: List[PlannedOrder] = Field(
        default_factory=list,
        description="List of new orders to be placed after any cancellations"
    )
    position_updates: Optional[List[PositionUpdate]] = None
    analysis: str = Field(..., description="Detailed analysis explaining the plan")

    def __init__(self, **data):
        super().__init__(**data)
        # Set order_link_id for each order using plan_id, session_id and order number
        for i, order in enumerate(self.orders, 1):
            order.set_order_link_id(self.id, self.session_id, i)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "plan1234",
                    "session_id": "ab12",
                    "created_at": "2024-01-04T10:00:00Z",
                    "parameters": {
                        "symbol": "BTCUSDT",
                        "budget": 1000.0,
                        "leverage": 2,
                        "timeframe": "Short (1-7d)",
                        "risk_level": "Medium"
                    },
                    "cancellations": [
                        {
                            "id": "1234567890",
                            "order_link_id": "old-plan-1",
                            "symbol": "BTCUSDT",
                            "reason": "Order no longer aligns with current market conditions"
                        }
                    ],
                    "orders": [],
                    "analysis": "Detailed market analysis and plan explanation"
                }
            ]
        }
    }

class PlanResponse(BaseModel):
    """Response from AI model including trading plan."""
    plan: TradingPlan = Field(..., description="Complete trading plan with orders")