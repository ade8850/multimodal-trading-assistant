# aitrading/tools/bybit/orders/validation.py

import math
from datetime import datetime, timezone
from typing import Dict
from rich.console import Console
from .utils import get_current_price

console = Console()

def calculate_quantity(budget: float, leverage: float, price: float, instrument_info: Dict) -> str:
    """Calculate order quantity considering lot size filters."""
    try:
        lot_size = instrument_info["lotSizeFilter"]
        min_qty = float(lot_size["minOrderQty"])
        qty_step = float(lot_size["qtyStep"])

        console.print("\n[yellow]Lot size filters:[/yellow]")
        console.print(f"Min quantity: {min_qty}")
        console.print(f"Quantity step: {qty_step}")

        # Calculate base quantity
        base_qty = budget / float(price)
        leveraged_qty = base_qty * leverage

        console.print(f"Base quantity: {base_qty}")
        console.print(f"Leveraged quantity: {leveraged_qty}")

        # Adjust to lot size
        decimal_places = str(qty_step)[::-1].find(".")
        if decimal_places > 0:
            qty = round(math.floor(leveraged_qty / qty_step) * qty_step, decimal_places)
        else:
            qty = math.floor(leveraged_qty / qty_step) * qty_step

        final_qty = str(max(qty, min_qty))
        console.print(f"[green]Final quantity: {final_qty}[/green]")
        return final_qty

    except Exception as e:
        raise Exception(f"Error calculating quantity: {str(e)}")


def verify_order_status(session, symbol: str, order_id: str) -> None:
    """Verify order status after placement."""
    try:
        # Check order status
        order_status = session.get_order_history(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        console.print("\n[yellow]Order Status:[/yellow]")
        console.print(order_status)

        # Check updated positions
        positions = session.get_positions(
            category="linear",
            symbol=symbol
        )
        console.print("\n[yellow]Updated Positions:[/yellow]")
        console.print(positions)

    except Exception as e:
        console.print(f"[red]Error verifying order status: {str(e)}[/red]")
        raise
