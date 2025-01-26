# aitrading/tools/bybit/orders/execution.py

from typing import Dict
import logfire
from .utils import get_current_price, get_instrument_info
from .validation import calculate_quantity


def execute_order_operations(session, order, instrument_info: Dict) -> Dict:
    """Execute order operations including base params preparation and order placement."""
    results = {"entry": None, "errors": []}

    try:
        # Prepare base order parameters
        base_params = _prepare_base_order_params(session, order, instrument_info)

        # Add TP/SL parameters if present
        order_params = _add_tp_sl_params(base_params, order.order.exit)

        # Place the order
        logfire.info("Placing order...")
        results["entry"] = session.place_order(**order_params)
        logfire.info(f"Order placed successfully", **results)

        # Verify order status
        verify_order_status(session, order.symbol, results["entry"]["result"]["orderId"])

        return results

    except Exception as e:
        error_msg = str(e)
        logfire.error(f"[red]Error in execute_order_operations: {error_msg}")
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
        logfire.error(f"Error rounding price: {str(e)}")
        raise


def set_trading_stops(session, symbol: str, position_idx: int = 0, **kwargs) -> Dict:
    """Set or update trading stop levels for a position."""
    try:
        # Prepare parameters
        params = {
            "category": "linear",
            "symbol": symbol,
            "positionIdx": position_idx
        }

        # Add optional parameters if provided
        price_params = ["takeProfit", "stopLoss", "tpLimitPrice", "slLimitPrice"]
        other_params = ["tpTriggerBy", "slTriggerBy", "tpSize", "slSize"]

        # Handle price parameters with proper rounding
        for param in price_params:
            if param in kwargs and kwargs[param] is not None:
                params[param] = round_price(kwargs[param], symbol, session)
                logfire.info(f"Rounded {param}", original=kwargs[param], rounded=params[param])

        # Handle non-price parameters
        for param in other_params:
            if param in kwargs and kwargs[param] is not None:
                params[param] = str(kwargs[param])

        # Make API request
        response = session.set_trading_stop(**params)

        if response["retCode"] != 0:
            raise ValueError(f"API error: {response['retMsg']}")

        logfire.info(f"Successfully updated trading stops for {symbol}")
        return response["result"]

    except Exception as e:
        raise Exception(f"Error setting trading stops for {symbol}: {str(e)}")


def cancel_order(session, symbol: str, order_id: str = None, order_link_id: str = None) -> Dict:
    """Cancel an order by order_id or order_link_id."""
    try:
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

        response = session.cancel_order(**params)

        if response["retCode"] != 0:
            raise ValueError(f"API error: {response['retMsg']}")

        logfire.info(f"Successfully cancelled order", order=(order_id or order_link_id))
        return response["result"]

    except Exception as e:
        raise Exception(f"Error cancelling order: {str(e)}")


def _prepare_base_order_params(session, order, instrument_info: Dict) -> Dict:
    """Prepare base order parameters."""
    try:
        # Calculate quantity
        price_for_qty = (
            order.order.entry.price
            if order.order.type == "limit"
            else get_current_price(session, order.symbol)
        )

        quantity = calculate_quantity(
            budget=order.order.entry.budget,
            leverage=order.order.entry.leverage,
            price=price_for_qty,
            instrument_info=instrument_info,
        )

        # Base parameters
        params = {
            "category": "linear",
            "symbol": order.symbol,
            "side": "Buy" if order.type == "long" else "Sell",
            "orderType": order.order.type.title(),
            "qty": quantity,
            "isLeverage": 1,
            "timeInForce": "GTC",
            "positionIdx": 0,
            "orderLinkId": order.order_link_id
        }

        # Add price for limit orders only
        if order.order.type == "limit":
            params["price"] = round_price(order.order.entry.price, order.symbol, session)

        return params

    except Exception as e:
        raise Exception(f"Error preparing order params for Order #{order.id}: {str(e)}")


def _add_tp_sl_params(base_params: Dict, exit_orders) -> Dict:
    """Add take profit and stop loss parameters."""
    try:
        order_params = base_params.copy()

        if not (exit_orders.take_profit or exit_orders.stop_loss):
            return order_params

        # Set tpslMode if we have either TP or SL
        order_params["tpslMode"] = "Full"

        if exit_orders.take_profit:
            order_params.update({
                "takeProfit": round_price(exit_orders.take_profit.price, order_params["symbol"], session),
                "tpTriggerBy": "LastPrice",
                "tpOrderType": "Market",
            })

        if exit_orders.stop_loss:
            order_params.update({
                "stopLoss": round_price(exit_orders.stop_loss.price, order_params["symbol"], session),
                "slTriggerBy": "LastPrice",
                "slOrderType": "Market",
            })

        return order_params

    except Exception as e:
        raise Exception(f"Error adding TP/SL params for {base_params.get('orderLinkId')}: {str(e)}")


def verify_order_status(session, symbol: str, order_id: str) -> None:
    """Verify order status after placement."""
    try:
        # Check order status
        order_status = session.get_order_history(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )

        # Check updated positions
        positions = session.get_positions(
            category="linear",
            symbol=symbol
        )

    except Exception as e:
        raise