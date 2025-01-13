# aitrading/tools/bybit/orders/utils.py

from typing import Dict, List
from rich.console import Console

console = Console()


def get_active_orders(session, symbol: str) -> List[Dict]:
    """Get active orders for a symbol."""
    try:
        # Get open orders
        response = session.get_open_orders(
            category="linear",
            symbol=symbol,
            orderFilter="Order"
        )

        if response["retCode"] != 0:
            raise ValueError(f"API error: {response['retMsg']}")

        orders = response["result"]["list"]

        # Format orders
        formatted_orders = []
        for order in orders:
            formatted = {
                "id": order["orderId"],
                "order_link_id": order.get("orderLinkId", ""),
                "symbol": order["symbol"],
                "type": order["orderType"],
                "side": order["side"],
                "price": float(order["price"]) if order["price"] != "0" else None,
                "qty": float(order["qty"]),
                "created_time": order["createdTime"],
                "updated_time": order["updatedTime"],
                "status": order["orderStatus"],
                "take_profit": float(order["takeProfit"]) if order.get("takeProfit") else None,
                "stop_loss": float(order["stopLoss"]) if order.get("stopLoss") else None
            }
            formatted_orders.append(formatted)

        console.print(f"Found {len(formatted_orders)} active orders for {symbol}")
        return formatted_orders

    except Exception as e:
        raise Exception(f"Error fetching active orders for {symbol}: {str(e)}")


def get_positions(session, symbol: str) -> List[Dict]:
    """Get current positions for a symbol."""
    try:
        response = session.get_positions(
            category="linear",
            symbol=symbol
        )

        if response["retCode"] != 0:
            raise ValueError(f"API error: {response['retMsg']}")

        positions = response["result"]["list"]

        # Format positions
        formatted_positions = []
        for pos in positions:
            if float(pos["size"]) == 0:  # Skip empty positions
                continue

            formatted = {
                "symbol": pos["symbol"],
                "side": pos["side"],
                "size": float(pos["size"]),
                "entry_price": float(pos["avgPrice"]),
                "leverage": float(pos["leverage"]),
                "unrealized_pnl": float(pos["unrealisedPnl"]),
                "take_profit": float(pos["takeProfit"]) if pos.get("takeProfit") else None,
                "stop_loss": float(pos["stopLoss"]) if pos.get("stopLoss") else None,
                "created_time": pos["createdTime"]
            }
            formatted_positions.append(formatted)

        console.print(f"Found {len(formatted_positions)} active positions for {symbol}")
        return formatted_positions

    except Exception as e:
        console.print(e)
        raise Exception(f"[red]Error fetching positions for {symbol}: {str(e)}[/red]")


def get_current_price(session, symbol: str) -> float:
    """Get current market price."""
    try:
        response = session.get_tickers(category="linear", symbol=symbol)
        return float(response["result"]["list"][0]["lastPrice"])
    except Exception as e:
        raise Exception(f"Error fetching price for {symbol}: {str(e)}")


def verify_account_status(session, symbol: str) -> None:
    """Verify account balance and positions before placing order."""
    try:
        # Check wallet balance
        balance = session.get_wallet_balance(
            accountType="UNIFIED",
            coin="USDT"
        )
        #console.print("\n[yellow]Account Balance:[/yellow]")
        #console.print(balance)

        # Check existing positions
        positions = session.get_positions(
            category="linear",
            symbol=symbol
        )
        #console.print("\n[yellow]Current Positions:[/yellow]")
        #console.print(positions)

    except Exception as e:
        console.print(f"[red]Error verifying account status: {str(e)}[/red]")
        raise


def get_instrument_info(session, symbol: str) -> Dict:
    """Get instrument trading rules."""
    try:
        response = session.get_instruments_info(
            category="linear", symbol=symbol
        )
        return response["result"]["list"][0]
    except Exception as e:
        raise Exception(f"Error fetching instrument info for {symbol}: {str(e)}")
