from typing import Dict, List, Any
import logfire
from ....models.position import Position
from ....models.orders import ExistingOrder


class BudgetCalculator:
    """Handles budget calculations and position limits."""
    
    def __init__(self, default_leverage: int = 3):
        """Initialize with default leverage.
        
        Args:
            default_leverage: Default leverage to use when not available from positions
        """
        self.default_leverage = default_leverage

    def calculate_positions_budget(self, positions: List[Position], current_price: float) -> float:
        """Calculate total budget allocated in open positions."""
        total_budget = 0.0
        for position in positions:
            try:
                if isinstance(position, dict):
                    # Legacy dictionary format
                    position_size = float(position["size"])
                    entry_price = float(position["entry_price"])
                    leverage = float(position["leverage"])
                else:
                    # New Position object
                    position_size = position.size
                    entry_price = position.entry_price
                    leverage = position.leverage

                # Calculate actual budget (position value / leverage)
                position_value = position_size * entry_price
                position_budget = position_value / leverage
                total_budget += position_budget

                logfire.debug("Position budget calculation",
                            size=position_size,
                            entry_price=entry_price,
                            leverage=leverage,
                            position_value=position_value,
                            position_budget=position_budget,
                            age_hours=getattr(position, 'age_hours', None),
                            is_in_profit=getattr(position, 'is_in_profit', lambda: None)())

            except Exception as e:
                logfire.error("Error calculating position budget",
                            error=str(e),
                            position=str(position))
                continue

        return total_budget

    def calculate_orders_budget(self, orders: List[ExistingOrder]) -> float:
        """Calculate total budget allocated in pending orders."""
        total_budget = 0.0
        for order in orders:
            try:
                # Handle different order object types
                if isinstance(order, ExistingOrder):
                    # For ExistingOrder objects
                    qty = float(order.qty)
                    price = float(order.price) if order.price is not None else 0
                    
                    # Use the default leverage from constructor
                    leverage = self.default_leverage
                    
                    # Calculate budget using the specified leverage
                    order_budget = (qty * price) / leverage if price > 0 else 0
                    
                    logfire.debug("Order budget calculated using default leverage",
                                order_id=order.id,
                                order_value=qty * price,
                                leverage=leverage,
                                order_budget=order_budget)
                else:
                    # For dictionary format orders (legacy)
                    qty = float(order["qty"])
                    price = float(order["price"]) if order["price"] is not None else 0
                    
                    # Use default leverage from constructor
                    leverage = self.default_leverage
                    
                    # Calculate budget
                    order_budget = (qty * price) / leverage if price > 0 else 0

                total_budget += order_budget

                logfire.debug("Order budget calculation",
                            type=order.type if isinstance(order, ExistingOrder) else order.get("type"),
                            qty=qty,
                            price=price,
                            leverage=leverage,
                            order_budget=order_budget,
                            age_hours=getattr(order, 'age_hours', None))

            except Exception as e:
                logfire.error("Error calculating order budget",
                            error=str(e),
                            order=str(order))
                continue

        return total_budget

    def calculate_allocated_budget(self, positions: List[Position], orders: List[ExistingOrder], current_price: float) -> tuple[float, float]:
        """Calculate total allocated budget and breakdown by positions and orders."""
        positions_budget = self.calculate_positions_budget(positions, current_price)
        orders_budget = self.calculate_orders_budget(orders)

        logfire.info("Budget allocation calculated",
                    positions_budget=positions_budget,
                    orders_budget=orders_budget,
                    total_allocated=positions_budget + orders_budget)

        return positions_budget, orders_budget

    def calculate_position_limits(self, positions: List[Position]) -> Dict[str, float]:
        """Calculate position-based limits for reduce-only orders."""
        try:
            limits = {
                "max_long_reduce": 0.0,
                "max_short_reduce": 0.0,
                "total_long_size": 0.0,
                "total_short_size": 0.0
            }

            for position in positions:
                position_size = float(position.size)
                if position.side.lower() == "buy":
                    limits["total_long_size"] += position_size
                    limits["max_long_reduce"] = max(limits["max_long_reduce"], position_size)
                else:
                    limits["total_short_size"] += position_size
                    limits["max_short_reduce"] = max(limits["max_short_reduce"], position_size)

            logfire.info("Position limits calculated", limits=limits)
            return limits

        except Exception as e:
            logfire.exception("Failed to calculate position limits", error=str(e))
            raise

    def calculate_available_budget(self,
                                total_budget: float,
                                positions_budget: float,
                                orders_budget: float,
                                position_limits: Dict[str, float]) -> Dict[str, float]:
        """Calculate available budget considering reduce-only orders.

        Args:
            total_budget: Total trading budget
            positions_budget: Budget allocated in positions
            orders_budget: Budget allocated in pending orders
            position_limits: Current position sizes and limits

        Returns:
            Dict containing:
            - standard: Available budget for new positions
            - reduce_only_long: Available size for reducing long positions
            - reduce_only_short: Available size for reducing short positions
            - total_long_available: Total long position size
            - total_short_available: Total short position size
        """
        try:
            # Calculate standard available budget (for new positions)
            base_available = total_budget - positions_budget - orders_budget

            # Calculate available for reduce-only based on position sizes
            available = {
                # Standard budget can't go below 0
                "standard": max(0.0, base_available),

                # Reduce-only limits are based on position sizes
                "reduce_only_long": position_limits["max_long_reduce"],
                "reduce_only_short": position_limits["max_short_reduce"],

                # Total position sizes for reference
                "total_long_available": position_limits["total_long_size"],
                "total_short_available": position_limits["total_short_size"]
            }

            logfire.info("Available budget calculated",
                        base_available=base_available,
                        standard=available["standard"],
                        reduce_only_long=available["reduce_only_long"],
                        reduce_only_short=available["reduce_only_short"],
                        total_long=available["total_long_available"],
                        total_short=available["total_short_available"])

            return available

        except Exception as e:
            logfire.exception("Failed to calculate available budget", error=str(e))
            raise