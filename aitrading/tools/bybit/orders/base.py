# aitrading/tools/bybit/orders/base.py

from typing import Dict, List, Any, Optional
from pybit.unified_trading import HTTP
from rich.console import Console
from .execution import execute_order_operations, set_trading_stops, cancel_order
from .utils import get_current_price, get_active_orders, get_positions, verify_account_status, get_instrument_info

console = Console()

class OrdersTool:
    """Tool for managing orders on Bybit."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """Initialize the Bybit client."""
        self.session = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)

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
            console.print(f"\n[yellow]Setting position settings for {symbol}[/yellow]")
            console.print(f"Leverage: {leverage}x")

            # Set leverage
            try:
                leverage_response = self.session.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(leverage),
                    sellLeverage=str(leverage),
                )
                console.print(f"Leverage response: {leverage_response}", style="green")
            except Exception as e:
                if "110043" not in str(e):  # Ignore "leverage already set"
                    console.print(f"[red]Error setting leverage: {str(e)}[/red]")
                    raise
                console.print(f"[yellow]Leverage already set to {leverage}x[/yellow]")

            # Set one-way mode
            try:
                mode_response = self.session.switch_position_mode(
                    category="linear", symbol=symbol, mode=0
                )
                console.print(f"Position mode response: {mode_response}", style="green")
            except Exception as e:
                if "110025" not in str(e) and "PositionModeIsAlreadyExist" not in str(e):
                    console.print(f"[red]Error setting position mode: {str(e)}[/red]")
                    raise
                console.print("[yellow]Position mode already set to one-way[/yellow]")

        except Exception as e:
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

            instrument_info = get_instrument_info(self.session, order.symbol)

            return execute_order_operations(self.session, order, instrument_info)

        except Exception as e:
            error_msg = str(e)
            console.print(f"[red]Error placing order: {error_msg}[/red]")
            results["errors"].append(error_msg)
            return results

    def set_trading_stops(self, symbol: str, position_idx: int = 0, **kwargs) -> Dict:
        """Set or update trading stop levels for a position."""
        return set_trading_stops(self.session, symbol, position_idx, **kwargs)