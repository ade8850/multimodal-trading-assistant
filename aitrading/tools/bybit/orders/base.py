# aitrading/tools/bybit/orders/base.py
import random
import string
from typing import Dict, List, Any, Optional
from pybit.unified_trading import HTTP
import logfire

from aitrading.models.position import Position
from .execution import execute_order_operations, set_trading_stops, cancel_order
from .utils import get_current_price, get_active_orders, get_positions, verify_account_status, get_instrument_info


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

            # Execute main order
            entry_result = execute_order_operations(self.session, order, instrument_info)
            results["entry"] = entry_result

            # Check if we have successful entry order placement
            if not entry_result.get("errors") and entry_result.get("entry"):
                # Handle exit order configuration if present
                if hasattr(order.order, "exit") and order.order.exit:
                    try:
                        with logfire.span("setup_exit_orders") as span:
                            span.set_attributes({
                                "symbol": order.symbol,
                                "order_link_id": order.order_link_id
                            })

                            # Configure take profit levels
                            if order.order.exit.take_profit:
                                for tp_level in order.order.exit.take_profit:
                                    self._place_exit_order(
                                        symbol=order.symbol,
                                        parent_id=entry_result["entry"]["result"]["orderId"],
                                        parent_link_id=order.order_link_id,
                                        exit_type="profit",
                                        side="Sell" if order.type == "long" else "Buy",
                                        price=tp_level.price,
                                        size_percentage=tp_level.size_percentage,
                                        trigger_price=tp_level.trigger_price
                                    )

                            # Configure stop loss levels
                            if order.order.exit.stop_loss:
                                for sl_level in order.order.exit.stop_loss:
                                    self._place_exit_order(
                                        symbol=order.symbol,
                                        parent_id=entry_result["entry"]["result"]["orderId"],
                                        parent_link_id=order.order_link_id,
                                        exit_type="protect",
                                        side="Sell" if order.type == "long" else "Buy",
                                        price=sl_level.price,
                                        size_percentage=sl_level.size_percentage,
                                        trigger_price=sl_level.trigger_price
                                    )

                    except Exception as e:
                        logfire.warning("Failed to set exit orders",
                                        symbol=order.symbol,
                                        order_link_id=order.order_link_id,
                                        error=str(e))
                        results["errors"].append(f"Exit orders setup failed: {str(e)}")

            return results

        except Exception as e:
            logfire.exception("Error placing strategy orders",
                              symbol=getattr(order, 'symbol', None),
                              order_link_id=getattr(order, 'order_link_id', None),
                              error=str(e))
            results["errors"].append(str(e))
            return results

    def _place_exit_order(
            self,
            symbol: str,
            parent_id: str,
            parent_link_id: str,
            exit_type: str,
            side: str,
            price: float,
            size_percentage: float,
            trigger_price: Optional[float] = None
    ) -> Dict:
        """Place an exit order (take profit or stop loss) with size as percentage of position."""
        try:
            with logfire.span("place_exit_order") as span:
                span.set_attributes({
                    "symbol": symbol,
                    "exit_type": exit_type,
                    "parent_id": parent_id,
                    "size_percentage": size_percentage
                })

                # Get current position size to calculate exit order size
                positions = self.get_positions(symbol)
                if not positions:
                    raise ValueError("No position found for exit order")

                current_position = positions[0]
                exit_size = float(current_position.size) * (size_percentage / 100)

                chrs = string.ascii_letters + string.digits
                rndstr = ''.join(random.choice(chrs) for _ in range(4))

                # always opposite
                if side == "Buy":
                    side = "Sell"
                elif side == "Sell":
                    side = "Buy"

                # Prepare order parameters
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": side,
                    "orderType": "Limit" if not trigger_price else "Trigger",
                    "qty": str(exit_size),
                    "price": str(price),
                    "reduceOnly": True,
                    "closeOnTrigger": True,
                    "orderLinkId": f"{parent_link_id}-{exit_type}-{size_percentage}-{rndstr}"
                }

                if trigger_price:
                    params["triggerPrice"] = str(trigger_price)
                    params["triggerBy"] = "LastPrice"

                logfire.info("Placing exit order",
                             symbol=symbol,
                             exit_type=exit_type,
                             size_percentage=size_percentage,
                             params=params)

                # Place the order
                response = self.session.place_order(**params)

                if response["retCode"] != 0:
                    raise ValueError(f"Failed to place exit order: {response['retMsg']}")

                logfire.info("Exit order placed successfully",
                             symbol=symbol,
                             exit_type=exit_type,
                             order_id=response["result"].get("orderId"))

                return response["result"]

        except Exception as e:
            logfire.exception("Failed to place exit order",
                              symbol=symbol,
                              exit_type=exit_type,
                              error=str(e))
            raise Exception(f"Error placing exit order: {str(e)}")

    def set_trading_stops(self, symbol: str, position_idx: int = 0, **kwargs) -> Dict:
        """Set or update trading stop levels for a position."""
        return set_trading_stops(self.session, symbol, position_idx, **kwargs)