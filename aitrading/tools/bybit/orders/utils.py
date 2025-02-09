# aitrading/tools/bybit/orders/utils.py

from typing import Dict, List
import logfire
from ....models.orders import ExistingOrder
from ....models.position import Position


def get_active_orders(session, symbol: str) -> List[ExistingOrder]:
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
            try:
                formatted_order = ExistingOrder.from_exchange_data(order)
                formatted_orders.append(formatted_order)
                
                logfire.debug("Processed order", 
                            order_id=formatted_order.id,
                            age_seconds=formatted_order.age_seconds,
                            status=formatted_order.status)
                
            except Exception as e:
                logfire.error("Failed to process order",
                            order=order,
                            error=str(e))
                continue

        logfire.info(f"Found {len(formatted_orders)} active orders", formatted_orders=formatted_orders)
        return formatted_orders

    except Exception as e:
        raise Exception(f"Error fetching active orders for {symbol}: {str(e)}")


def get_positions(session, symbol: str) -> List[Position]:
    """Get current positions for a symbol."""
    try:
        response = session.get_positions(
            category="linear",
            symbol=symbol
        )

        if response["retCode"] != 0:
            raise ValueError(f"API error: {response['retMsg']}")

        positions = response["result"]["list"]
        
        # Log raw response
        logfire.debug("Raw positions response", 
                     positions=positions,
                     response_type=str(type(positions)))

        # Format positions
        formatted_positions = []
        for pos in positions:
            try:
                # Skip empty positions
                if float(pos["size"]) == 0:
                    continue

                logfire.debug("Processing position data", 
                            raw_position=pos,
                            created_time=pos.get("createdTime"),
                            created_time_type=str(type(pos.get("createdTime"))))

                position = Position.from_exchange_data(pos)
                formatted_positions.append(position)

                logfire.debug("Processed position",
                            symbol=position.symbol,
                            side=position.side,
                            created_at=position.created_at.isoformat() if position.created_at else None,
                            age_seconds=position.age_seconds,
                            is_in_profit=position.is_in_profit(),
                            margin_used=position.margin_used)

            except Exception as e:
                logfire.error("Failed to process position",
                            position=pos,
                            error=str(e))
                continue

        logfire.info(f"Found {len(formatted_positions)} active positions", 
                    count=len(formatted_positions),
                    positions=[{
                        "symbol": p.symbol,
                        "side": p.side,
                        "size": p.size,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                        "is_in_profit": p.is_in_profit()
                    } for p in formatted_positions])
        
        return formatted_positions

    except Exception as e:
        raise Exception(f"Error fetching positions for {symbol}: {str(e)}")


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

        # Check existing positions
        positions = session.get_positions(
            category="linear",
            symbol=symbol
        )

    except Exception as e:
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
