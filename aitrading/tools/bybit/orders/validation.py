# aitrading/tools/bybit/orders/validation.py

import math
from datetime import datetime, timezone
from typing import Dict, Optional
import logfire


def calculate_quantity(
        budget: float,
        leverage: float,
        price: float,
        instrument_info: Dict,
        is_reduce_only: bool = False,
        base_position_size: Optional[float] = None,
        size_percentage: Optional[float] = None
) -> str:
    """Calculate order quantity considering lot size filters and order type.

    Args:
        budget: Available budget for the order
        leverage: Trading leverage
        price: Entry price for calculation
        instrument_info: Trading pair information from exchange
        is_reduce_only: Whether this is a reduce-only order
        base_position_size: Base position size for reduce-only orders
        size_percentage: Percentage of base position to use (for partial exits)

    Returns:
        Formatted quantity string that satisfies lot size requirements
    """
    try:
        with logfire.span("calculate_quantity") as span:
            span.set_attributes({
                "budget": budget,
                "leverage": leverage,
                "price": price,
                "is_reduce_only": is_reduce_only
            })

            lot_size = instrument_info["lotSizeFilter"]
            min_qty = float(lot_size["minOrderQty"])
            qty_step = float(lot_size["qtyStep"])

            logfire.debug("Lot size filters",
                          min_quantity=min_qty,
                          quantity_step=qty_step)

            if is_reduce_only:
                if not base_position_size:
                    raise ValueError("Base position size required for reduce-only orders")

                # Calculate quantity based on percentage of base position
                if size_percentage:
                    raw_qty = base_position_size * (size_percentage / 100.0)
                else:
                    raw_qty = base_position_size

                logfire.debug("Reduce-only quantity calculation",
                              base_size=base_position_size,
                              percentage=size_percentage,
                              raw_quantity=raw_qty)
            else:
                # Calculate standard entry quantity
                base_qty = budget / float(price)
                raw_qty = base_qty * leverage

                logfire.debug("Standard quantity calculation",
                              base_quantity=base_qty,
                              leveraged_quantity=raw_qty)

            # Adjust to lot size constraints
            decimal_places = str(qty_step)[::-1].find(".")
            if decimal_places > 0:
                qty = round(math.floor(raw_qty / qty_step) * qty_step, decimal_places)
            else:
                qty = math.floor(raw_qty / qty_step) * qty_step

            # Ensure minimum quantity
            final_qty = str(max(qty, min_qty))

            logfire.info("Quantity calculation completed",
                         raw_quantity=raw_qty,
                         final_quantity=final_qty,
                         is_reduce_only=is_reduce_only)

            return final_qty

    except Exception as e:
        logfire.exception("Error calculating quantity",
                          error=str(e),
                          budget=budget,
                          leverage=leverage,
                          price=price)
        raise ValueError(f"Error calculating quantity: {str(e)}")


def validate_trigger_price(
        trigger_price: float,
        current_price: float,
        order_side: str,
        order_type: str
) -> None:
    """Validate trigger price for conditional orders.

    Args:
        trigger_price: Trigger price to validate
        current_price: Current market price
        order_side: Order side (Buy/Sell)
        order_type: Order type (e.g. 'Limit', 'Market')

    Raises:
        ValueError: If trigger price validation fails
    """
    try:
        with logfire.span("validate_trigger_price") as span:
            span.set_attributes({
                "trigger_price": trigger_price,
                "current_price": current_price,
                "order_side": order_side,
                "order_type": order_type
            })

        if order_side == "Buy":
            if trigger_price <= current_price:
                raise ValueError(
                    "Buy stop orders must have trigger price above current price"
                )
        else:  # Sell
            if trigger_price >= current_price:
                raise ValueError(
                    "Sell stop orders must have trigger price below current price"
                )

        logfire.info("Trigger price validated successfully",
                     trigger_price=trigger_price,
                     current_price=current_price,
                     order_side=order_side)

    except Exception as e:
        logfire.error("Trigger price validation failed",
                      error=str(e),
                      trigger_price=trigger_price,
                      current_price=current_price,
                      order_side=order_side)
        raise


def verify_order_status(session, symbol: str, order_id: str) -> None:
    """Verify order status after placement.

    Args:
        session: Trading session
        symbol: Trading pair symbol
        order_id: Order ID to verify
    """
    try:
        with logfire.span("verify_order_status") as span:
            span.set_attributes({
                "symbol": symbol,
                "order_id": order_id
            })

            # Check order status
            order_status = session.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )

            logfire.info("Order status retrieved",
                         symbol=symbol,
                         order_id=order_id,
                         status=order_status["result"]["orderStatus"])

            # Check updated positions
            positions = session.get_positions(
                category="linear",
                symbol=symbol
            )

            logfire.info("Position status checked",
                         symbol=symbol,
                         positions_count=len(positions["result"]["list"]))

    except Exception as e:
        logfire.exception("Failed to verify order status",
                          symbol=symbol,
                          order_id=order_id,
                          error=str(e))
        raise