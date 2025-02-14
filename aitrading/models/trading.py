# aitrading/models/trading.py
import time
from typing import List, Optional, Dict, Literal, Union, Any
from datetime import datetime

import logfire
from pydantic import BaseModel, Field, validator
from enum import Enum

from .base import generate_uuid_short
from .orders import Order, OrderCancellation, OrderRole
from .strategy import StrategicContext

class ExecutionMode(str, Enum):
    """Mode of execution for the trading system."""
    SCHEDULER = "scheduler"  # Continuous monitoring with fixed intervals
    MANUAL = "manual"     # One-time analysis via UI

class TradingParameters(BaseModel):
    """Input parameters for trading plan generation."""
    symbol: str
    budget: float = Field(ge=10)
    leverage: int = Field(ge=1, le=100)
    stop_loss_config: Optional[Dict] = Field(
        default=None,
        description="Optional configuration for automated stop loss management"
    )
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.MANUAL,
        description="Whether this is a scheduler run or manual analysis"
    )
    analysis_interval: Optional[int] = Field(
        default=None,
        description="Minutes between analyses for scheduler mode"
    )

    @validator('analysis_interval')
    def validate_interval(cls, v, values):
        """Validate that interval is set for scheduler mode."""
        if values.get('execution_mode') == ExecutionMode.SCHEDULER and v is None:
            raise ValueError("analysis_interval must be set when execution_mode is scheduler")
        return v

    class Config:
        use_enum_values = True

# Il resto delle classi rimane invariato
class Range24h(BaseModel):
    """24-hour price range."""
    high: float
    low: float

class OrderExecutionType(str, Enum):
    """Specifies how the order should be executed."""
    IMMEDIATE = "immediate"    # Execute immediately at market
    PASSIVE = "passive"        # Wait for price to reach level
    TRIGGER = "trigger"        # Execute when condition met
    BRACKET = "bracket"        # Part of a bracket order setup

class RiskLevel(str, Enum):
    """Risk level for the order."""
    CRITICAL = "critical"      # Must execute quickly
    NORMAL = "normal"         # Standard execution
    MINIMAL = "minimal"       # Can wait for better price


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
    analysis: str = Field(..., description="Detailed analysis explaining the plan")

    def __init__(self, **data):
        super().__init__(**data)
        # Set order_link_id for each order using plan_id, session_id and order number
        for i, order in enumerate(self.orders, 1):
            order.set_order_link_id(self.id, self.session_id, i)

    @validator('orders')
    def validate_orders(cls, v: List[PlannedOrder], values: Dict[str, Any]) -> List[PlannedOrder]:
        """Validate the complete set of orders in the plan."""
        if not v:
            return v

        # Track order IDs to ensure uniqueness
        order_ids = set()
        order_link_ids = set()

        for order in v:
            # Check ID uniqueness
            if order.id in order_ids:
                raise ValueError(f"Duplicate order ID: {order.id}")
            order_ids.add(order.id)

            # Check order link ID uniqueness
            if order.order_link_id:
                if order.order_link_id in order_link_ids:
                    raise ValueError(f"Duplicate order link ID: {order.order_link_id}")
                order_link_ids.add(order.order_link_id)

        return v

    def get_total_budget_required(self) -> float:
        """Calculate total budget required for all orders."""
        return sum(order.order.entry.budget for order in self.orders)

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
                        "stop_loss_config": {
                            "timeframe": "1H",
                            "initial_multiplier": 1.5,
                            "in_profit_multiplier": 2.0
                        }
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