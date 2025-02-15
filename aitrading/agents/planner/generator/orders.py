from typing import Dict, List, Any, Optional
import logfire

from ....models.trading import PlannedOrder, TradingParameters
from ....models.strategy import StrategicContext
from ....models.position import Position
from ....models.orders import ExistingOrder
from ....tools.redis.order_context import OrderContext

class OrderProcessor:
    """Handles order processing and validation."""
    
    def __init__(self, order_context: OrderContext):
        """Initialize with order context manager."""
        self.order_context = order_context

    def process_existing_orders(self, orders: List[ExistingOrder]) -> List[Dict[str, Any]]:
        """Process existing orders and their strategic context."""
        try:
            processed_orders = []
            for order in orders:
                try:
                    # Convert order to dict
                    order_dict = self._convert_order_to_dict(order)

                    # Load and process strategic context
                    context_data = self.order_context.get_context(order.order_link_id)
                    if context_data and "data" in context_data:
                        context = StrategicContext(**context_data["data"])
                        # Ensure strategic context is properly structured
                        order_dict["strategic_context"] = {
                            "setup_rationale": context.setup_rationale,
                            "market_bias": context.market_bias,
                            "key_levels": context.key_levels,
                            "catalysts": context.catalysts,
                            "invalidation_conditions": context.invalidation_conditions
                        }
                    else:
                        # Provide empty but structured strategic context
                        order_dict["strategic_context"] = {
                            "setup_rationale": "Not available",
                            "market_bias": "Not available",
                            "key_levels": [],
                            "catalysts": [],
                            "invalidation_conditions": []
                        }

                    processed_orders.append(order_dict)

                    logfire.debug("Processed order with context",
                                order_id=order.id,
                                order_link_id=order.order_link_id,
                                has_context=bool(context_data))

                except Exception as e:
                    logfire.error("Failed to process order",
                                order_id=order.id,
                                order_link_id=order.order_link_id,
                                error=str(e))
                    continue

            return processed_orders

        except Exception as e:
            logfire.exception("Failed to process existing orders", error=str(e))
            raise

    def create_trading_plan_orders(self, 
                                 plan_data: Dict[str, Any], 
                                 params: TradingParameters,
                                 current_positions: List[Position]) -> List[PlannedOrder]:
        """Create and validate orders for a trading plan."""
        try:
            # Process orders - check for reduce-only conditions
            processed_orders = []

            for order_data in plan_data.get('orders', []):
                try:
                    # Ensure order_data is a dictionary
                    if isinstance(order_data, PlannedOrder):
                        order_data = order_data.model_dump()
                    elif not isinstance(order_data, dict):
                        raise ValueError(f"Invalid order data type: {type(order_data)}")

                    # Determine if the order should be reduce-only by checking against current positions
                    is_reduce_only = self._determine_reduce_only(order_data, current_positions)

                    # Set leverage from current position for reduce-only orders
                    if is_reduce_only and current_positions:
                        current_position = current_positions[0]
                        if "order" in order_data and "entry" in order_data["order"]:
                            order_data["order"]["entry"]["leverage"] = current_position.leverage

                    # Set reduce_only flag explicitly
                    order_data["reduce_only"] = is_reduce_only

                    # Add order to processed list
                    processed_orders.append(order_data)

                    logfire.debug("Processed order",
                                order_data=order_data,
                                reduce_only=is_reduce_only)

                except Exception as e:
                    logfire.error("Error processing order",
                                error=str(e),
                                order_data=order_data)
                    raise

            return processed_orders

        except Exception as e:
            logfire.error("Failed to create trading plan orders", error=str(e))
            raise

    def _determine_reduce_only(self, order_data: Dict[str, Any], current_positions: List[Position]) -> bool:
        """Determine if an order should be reduce-only based on current positions."""
        if not current_positions:
            return False

        current_position = current_positions[0]
        return (
            (current_position.side == "Buy" and order_data["type"] == "short") or
            (current_position.side == "Sell" and order_data["type"] == "long")
        )

    def _convert_order_to_dict(self, order: ExistingOrder) -> Dict[str, Any]:
        """Convert ExistingOrder to dictionary format."""
        from .utils import convert_pydantic_to_dict
        return convert_pydantic_to_dict(order)

    def save_strategic_context(self, order: PlannedOrder) -> bool:
        """Save strategic context for an order."""
        if not hasattr(order, 'strategic_context'):
            return True

        success = self.order_context.save_context(
            order_link_id=order.order_link_id,
            context=order.strategic_context
        )

        if not success:
            logfire.warning("Failed to save strategic context",
                          order_link_id=order.order_link_id)

        return success