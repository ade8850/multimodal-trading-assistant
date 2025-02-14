# aitrading/tools/bybit/orders/execution.py

from typing import Dict, Optional
import logfire
from .utils import get_current_price, get_instrument_info
from .validation import calculate_quantity


def execute_order_operations(
        session,
        order,
        instrument_info: Dict,
        is_reduce_only: bool = False,
        base_position_size: Optional[float] = None
) -> Dict:
    """Execute order operations including base params preparation and order placement.

    Args:
        session: Trading session
        order: Order to execute
        instrument_info: Instrument trading rules
        is_reduce_only: Whether this is a reduce-only order
        base_position_size: Base position size for reduce-only orders
    """
    results = {"entry": None, "errors": []}

    try:
        with logfire.span("execute_order_operations") as span:
            span.set_attributes({
                "order_id": order.id,
                "order_link_id": order.order_link_id,
                "symbol": order.symbol,
                "is_reduce_only": is_reduce_only
            })

            # Prepare base order parameters
            base_params = _prepare_base_order_params(
                session,
                order,
                instrument_info,
                is_reduce_only=is_reduce_only,
                base_position_size=base_position_size
            )

            # Add order parameters based on order type
            order_params = _prepare_order_params(base_params, order)

            # Place the order
            logfire.info("Placing order...",
                         is_reduce_only=is_reduce_only,
                         **order_params)
            results["entry"] = session.place_order(**order_params)
            logfire.info("Order placed successfully", result=results["entry"])

            # Verify order status
            verify_order_status(session, order.symbol, results["entry"]["result"]["orderId"])

            return results

    except Exception as e:
        error_msg = str(e)
        logfire.exception("Error in execute_order_operations", error=error_msg)
        results["errors"].append(error_msg)
        return results


def round_price(price: float, symbol: str, session) -> str:
    """Round price to instrument precision and convert to string."""
    try:
        info = get_instrument_info(session, symbol)
        price_scale = int(info.get("priceScale", "2"))  # Convert string to int
        rounded = round(float(price), price_scale)
        return f"{rounded:.{price_scale}f}"
    except Exception as e:
        logfire.error("Error rounding price", error=str(e))
        raise


def set_trading_stops(session, symbol: str, position_idx: int = 0, **kwargs) -> Dict:
    """Set or update trading stop levels for a position."""
    try:
        with logfire.span("set_trading_stops") as span:
            span.set_attributes({
                "symbol": symbol,
                "position_idx": position_idx
            })

            # Prepare parameters
            params = {
                "category": "linear",
                "symbol": symbol,
                "positionIdx": position_idx
            }

            # Add optional parameters if provided
            price_params = ["takeProfit", "stopLoss", "tpLimitPrice", "slLimitPrice"]
            other_params = ["tpTriggerBy", "slTriggerBy", "tpSize", "slSize", "tpslMode"]

            # Handle price parameters with proper rounding
            for param in price_params:
                if param in kwargs and kwargs[param] is not None:
                    params[param] = round_price(kwargs[param], symbol, session)
                    logfire.info(f"Rounded {param}",
                              original=kwargs[param],
                              rounded=params[param])

            # Handle non-price parameters
            for param in other_params:
                if param in kwargs and kwargs[param] is not None:
                    params[param] = str(kwargs[param])

            logfire.info("Setting trading stops", params=params)

            # Make API request
            response = session.set_trading_stop(**params)

            if response["retCode"] != 0:
                raise ValueError(f"API error: {response['retMsg']}")

            logfire.info(f"Successfully updated trading stops",
                       symbol=symbol,
                       response=response["result"])
            return response["result"]

    except Exception as e:
        logfire.exception("Error setting trading stops",
                       symbol=symbol,
                       error=str(e))
        raise Exception(f"Error setting trading stops for {symbol}: {str(e)}")


def cancel_order(session, symbol: str, order_id: str = None, order_link_id: str = None) -> Dict:
    """Cancel an order by order_id or order_link_id."""
    try:
        with logfire.span("cancel_order") as span:
            span.set_attributes({
                "symbol": symbol,
                "order_id": order_id,
                "order_link_id": order_link_id
            })

            if not (order_id or order_link_id):
                raise ValueError("Either order_id or order_link_id must be provided")

            params = {
                "category": "linear",
                "symbol": symbol
            }

            if order_id:
                params["orderId"] = order_id
            if order_link_id:
                params["orderLinkId"] = order_link_id

            logfire.info("Cancelling order", params=params)
            response = session.cancel_order(**params)

            if response["retCode"] != 0:
                raise ValueError(f"API error: {response['retMsg']}")

            logfire.info("Order cancelled successfully",
                       order=(order_id or order_link_id))
            return response["result"]

    except Exception as e:
        logfire.exception("Error cancelling order", error=str(e))
        raise Exception(f"Error cancelling order: {str(e)}")


def _prepare_base_order_params(
        session,
        order,
        instrument_info: Dict,
        is_reduce_only: bool = False,
        base_position_size: Optional[float] = None
) -> Dict:
    """Prepare base order parameters.

    Args:
        session: Trading session
        order: Order to prepare parameters for
        instrument_info: Instrument trading rules
        is_reduce_only: Whether this is a reduce-only order
        base_position_size: Base position size for reduce-only orders
    """
    try:
        with logfire.span("prepare_base_params"):
            # Calculate quantity
            price_for_qty = (
                order.order.entry.price
                if order.order.type == "limit"
                else get_current_price(session, order.symbol)
            )

            size_percentage = getattr(order.order.entry, 'size_percentage', None)

            quantity = calculate_quantity(
                budget=order.order.entry.budget,
                leverage=order.order.entry.leverage,
                price=price_for_qty,
                instrument_info=instrument_info,
                is_reduce_only=is_reduce_only,
                base_position_size=base_position_size,
                size_percentage=size_percentage
            )

            # Base parameters
            params = {
                "category": "linear",
                "symbol": order.symbol,
                "side": "Buy" if order.type == "long" else "Sell",
                "orderType": order.order.type.title(),
                "qty": quantity,
                "isLeverage": 0 if is_reduce_only else 1,  # No leverage for reduce-only
                "timeInForce": "GTC",
                "positionIdx": 0,
                "orderLinkId": order.order_link_id
            }

            # Add reduce-only flags if applicable
            if is_reduce_only:
                params["reduceOnly"] = True
                params["closeOnTrigger"] = True

            # Add price for limit orders only
            if order.order.type == "limit":
                params["price"] = round_price(order.order.entry.price, order.symbol, session)

            logfire.info("Prepared base parameters",
                         is_reduce_only=is_reduce_only,
                         params=params)
            return params

    except Exception as e:
        logfire.exception("Error preparing order params",
                          order_id=order.id,
                          error=str(e))
        raise Exception(f"Error preparing order params for Order #{order.id}: {str(e)}")


def _prepare_order_params(base_params: Dict, order) -> Dict:
    """Prepare final order parameters including any conditional parameters."""
    try:
        with logfire.span("prepare_order_params"):
            order_params = base_params.copy()

            # Add trigger parameters for conditional orders
            if hasattr(order, 'trigger_price') and order.trigger_price:
                order_params["triggerPrice"] = str(order.trigger_price)
                order_params["triggerBy"] = "LastPrice"
                # Convert to trigger order type if needed
                if order_params["orderType"] == "Limit":
                    order_params["orderType"] = "Trigger"

            logfire.info("Prepared order parameters", params=order_params)
            return order_params

    except Exception as e:
        logfire.exception("Error preparing order parameters", error=str(e))
        raise Exception(f"Error preparing order parameters: {str(e)}")


def verify_order_status(session, symbol: str, order_id: str) -> None:
    """Verify order status after placement."""
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
            logfire.info("Order status verified", status=order_status)

            # Check updated positions
            positions = session.get_positions(
                category="linear",
                symbol=symbol
            )
            logfire.info("Position status checked", positions=positions)

    except Exception as e:
        logfire.exception("Error verifying order status",
                       symbol=symbol,
                       order_id=order_id,
                       error=str(e))
        raise