# aitrading/tools/bybit/orders/execution.py

from typing import Dict

from rich.console import Console

from .utils import get_current_price
from .validation import calculate_quantity

console = Console()


def execute_order_operations(session, order, instrument_info: Dict) -> Dict:
    """Execute order operations including base params preparation and order placement."""
    results = {"entry": None, "errors": []}

    try:
        # Prepare base order parameters
        base_params = _prepare_base_order_params(session, order, instrument_info)
        #console.print("\n[yellow]Prepared order parameters:[/yellow]")
        #console.print(base_params)

        # Add TP/SL parameters if present
        order_params = _add_tp_sl_params(base_params, order.order.exit)
        #console.print("\n[yellow]Final order parameters with TP/SL:[/yellow]")
        #console.print(order_params)

        # Place the order
        console.print("\n[yellow]Placing order...[/yellow]")
        results["entry"] = session.place_order(**order_params)
        console.print(f"[green]Order placed successfully: {results['entry']}[/green]")

        # Verify order status
        verify_order_status(session, order.symbol, results["entry"]["result"]["orderId"])

        return results

    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]Error in execute_order_operations: {error_msg}[/red]")
        results["errors"].append(error_msg)
        return results


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
        valid_params = [
            "takeProfit", "stopLoss", "tpTriggerBy", "slTriggerBy",
            "tpSize", "slSize", "tpLimitPrice", "slLimitPrice"
        ]

        for param in valid_params:
            if param in kwargs and kwargs[param] is not None:
                params[param] = str(kwargs[param])

        # Make API request
        response = session.set_trading_stop(**params)

        if response["retCode"] != 0:
            raise ValueError(f"API error: {response['retMsg']}")

        console.print(f"[green]Successfully updated trading stops for {symbol}[/green]")
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

        console.print(f"Successfully cancelled order: {order_id or order_link_id}")
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

        console.print(f"\n[yellow]Calculated quantity:[/yellow] {quantity}")

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

        # Add price for limit orders
        if order.order.type == "limit":
            params["price"] = str(order.order.entry.price)

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
                "takeProfit": str(exit_orders.take_profit.price),
                "tpTriggerBy": "LastPrice",
                "tpOrderType": "Market",
            })

        if exit_orders.stop_loss:
            order_params.update({
                "stopLoss": str(exit_orders.stop_loss.price),
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
        #console.print("\n[yellow]Order Status:[/yellow]")
        #console.print(order_status)

        # Check updated positions
        positions = session.get_positions(
            category="linear",
            symbol=symbol
        )
        #console.print("\n[yellow]Updated Positions:[/yellow]")
        #console.print(positions)

    except Exception as e:
        console.print(f"[red]Error verifying order status: {str(e)}[/red]")
        raise
