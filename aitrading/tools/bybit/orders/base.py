# aitrading/tools/bybit/orders/base.py
import random
import string
from typing import Dict, List, Any, Optional
from pybit.unified_trading import HTTP
import logfire

from aitrading.models.position import Position
from .execution import execute_order_operations, set_trading_stops, cancel_order
from .utils import get_current_price, get_active_orders, get_positions, verify_account_status, get_instrument_info

from ....models import PlannedOrder

class OrdersTool:
    """Tool for managing orders on Bybit."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """Initialize the Bybit client."""
        self.session = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
        logfire.info("Bybit orders tool initialized", testnet=testnet)

    def get_active_orders(self, symbol: str) -> List[Dict]:
        """Get active orders for a symbol."""
        return get_active_orders(self.session, symbol)

    def get_positions(self, symbol: str) -> List[Dict]:
        """Get current positions for a symbol."""
        return get_positions(self.session, symbol)

    def cancel_order(self, symbol: str, order_id: str = None, order_link_id: str = None) -> Dict:
        """Cancel an order by order_id or order_link_id."""
        return cancel_order(self.session, symbol, order_id, order_link_id)

    def set_position_settings(self, symbol: str, leverage: int) -> None:
        """Configure leverage and position mode."""
        try:
            with logfire.span("set_position_settings") as span:
                span.set_attributes({
                    "symbol": symbol,
                    "leverage": leverage
                })

                logfire.info("Setting position settings",
                             symbol=symbol,
                             leverage=leverage)

                # Set leverage
                try:
                    leverage_response = self.session.set_leverage(
                        category="linear",
                        symbol=symbol,
                        buyLeverage=str(leverage),
                        sellLeverage=str(leverage),
                    )
                    logfire.info("Leverage set successfully",
                                 symbol=symbol,
                                 leverage=leverage,
                                 response=leverage_response)
                except Exception as e:
                    if "110043" not in str(e):  # Ignore "leverage already set"
                        logfire.error("Error setting leverage",
                                      symbol=symbol,
                                      leverage=leverage,
                                      error=str(e))
                        raise
                    logfire.info("Leverage already set",
                                 symbol=symbol,
                                 leverage=leverage)

                # Set one-way mode
                try:
                    mode_response = self.session.switch_position_mode(
                        category="linear", symbol=symbol, mode=0
                    )
                    logfire.info("Position mode set successfully",
                                 symbol=symbol,
                                 mode="one-way",
                                 response=mode_response)
                except Exception as e:
                    if "110025" not in str(e) and "PositionModeIsAlreadyExist" not in str(e):
                        logfire.error("Error setting position mode",
                                      symbol=symbol,
                                      error=str(e))
                        raise
                    logfire.info("Position mode already set to one-way",
                                 symbol=symbol)

        except Exception as e:
            logfire.exception("Failed to configure position settings",
                              symbol=symbol,
                              leverage=leverage,
                              error=str(e))
            raise Exception(f"Error configuring position for {symbol}: {str(e)}")

    def get_current_price(self, symbol: str) -> float:
        """Get current market price."""
        return get_current_price(self.session, symbol)

    def place_strategy_orders(self, order) -> Dict:
        """Place order on the exchange with orderLinkId."""
        try:
            results = {"entry": None, "errors": []}

            if not order.order_link_id:
                raise ValueError(f"Order #{order.id} missing order_link_id")

            # Verify account status before placing order
            verify_account_status(self.session, order.symbol)

            # Get instrument info
            instrument_info = get_instrument_info(self.session, order.symbol)

            # Se l'ordine è reduce-only, verifica che esista una posizione e che la direzione sia corretta
            current_positions = self.get_positions(order.symbol)

            # Convert order to dictionary and ensure reduce_only is present
            order_data = order.model_dump()
            order_data["reduce_only"] = order_data.get("reduce_only", False)

            # Recreate order with reduce_only field
            order = PlannedOrder.model_validate(order_data)

            if order.reduce_only:
                if not current_positions:
                    raise ValueError("Cannot place reduce-only order: no position exists")

                current_position = current_positions[0]
                valid_direction = (
                        (current_position.side == "Buy" and order.type == "short") or
                        (current_position.side == "Sell" and order.type == "long")
                )
                if not valid_direction:
                    raise ValueError(
                        f"Invalid reduce-only order direction: order {order.type} "
                        f"for position {current_position.side}"
                    )

                base_position_size = current_position.size
                logfire.info("Processing reduce-only order",
                             position_side=current_position.side,
                             order_type=order.type,
                             position_size=base_position_size)
            else:
                base_position_size = None

            # Execute order
            entry_result = execute_order_operations(
                self.session,
                order,
                instrument_info,
                is_reduce_only=order.reduce_only,
                base_position_size=base_position_size
            )
            results["entry"] = entry_result

            # Check if we have successful entry order placement
            if not entry_result.get("errors") and entry_result.get("entry"):
                logfire.info("Order placed successfully",
                             is_reduce_only=order.reduce_only,
                             order_id=order.order_link_id)

            return results

        except Exception as e:
            logfire.exception("Error placing strategy orders",
                              symbol=getattr(order, 'symbol', None),
                              order_link_id=getattr(order, 'order_link_id', None),
                              error=str(e))
            results["errors"].append(str(e))
            return results

    def set_trading_stops(self, symbol: str, position_idx: int = 0, **kwargs) -> Dict:
        """Set or update trading stop levels for a position."""
        return set_trading_stops(self.session, symbol, position_idx, **kwargs)