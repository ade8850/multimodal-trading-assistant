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
        size_percentage: Optional[float] = None,
        prevent_position_close: bool = False
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
        prevent_position_close: If True, ensures the position is not closed completely

    Returns:
        Formatted quantity string that satisfies lot size requirements
    """
    prevent_position_close = False  # FORCED
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

                # Usa il budget come fonte primaria per calcolare la quantità
                if budget > 0:
                    raw_qty = (budget * leverage) / price
                # Se il budget non è specificato, usa size_percentage come fallback
                elif size_percentage:
                    raw_qty = base_position_size * (size_percentage / 100.0)
                else:
                    # Se né budget né size_percentage sono specificati, usa l'intera posizione
                    # ma solo se prevent_position_close è False
                    if prevent_position_close:
                        # In questo caso, dovremmo logare un errore ma non modificare arbitrariamente la quantità
                        logfire.error("No valid budget or size_percentage for reduce-only order",
                                     base_size=base_position_size)
                        raise ValueError("Budget or size_percentage required for reduce-only orders with prevent_position_close=True")
                    else:
                        raw_qty = base_position_size
                        logfire.warning("Using entire position size for reduce-only order",
                                     base_size=base_position_size)

                # Se prevent_position_close è True, verifica che non si chiuda completamente la posizione
                if prevent_position_close and raw_qty >= base_position_size:
                    # Riduci leggermente la quantità per evitare la chiusura completa
                    min_qty = float(lot_size["minOrderQty"])
                    reserved_qty = max(min_qty, base_position_size * 0.01)  # Mantieni almeno 1% o min_qty
                    raw_qty = base_position_size - reserved_qty
                    logfire.warning("Adjusted quantity to prevent full position closure",
                                  original=base_position_size,
                                  adjusted=raw_qty,
                                  reserved=reserved_qty)

                logfire.debug("Reduce-only quantity calculation",
                            base_size=base_position_size,
                            budget=budget,
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
            final_qty = max(qty, min_qty)

            # Per ordini reduce-only, controlliamo se stiamo tentando di chiudere quasi tutta la posizione
            if is_reduce_only and raw_qty >= base_position_size * 0.98:
                # Se il risultato dell'arrotondamento è inferiore alla dimensione della posizione
                # e la differenza è piccola, usiamo la dimensione esatta della posizione
                if final_qty < base_position_size and base_position_size - final_qty <= qty_step * 2:
                    final_qty = base_position_size
                    logfire.info("Adjusted reduce-only quantity to match position size exactly",
                                original_qty=qty,
                                adjusted_qty=final_qty,
                                base_position_size=base_position_size)

            # For reduce-only orders, ensure quantity doesn't exceed position size
            if is_reduce_only and final_qty > base_position_size:
                logfire.warning("Reduce-only quantity exceeds position size, adjusting",
                              calculated_qty=final_qty,
                              position_size=base_position_size)
                final_qty = base_position_size
            
            final_qty = str(final_qty)  # Conversione a stringa come richiesto dal resto del codice

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