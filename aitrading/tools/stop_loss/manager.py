from typing import Dict, List, Any, Optional
import logfire
import time

from .models import StopLossConfig, StopLossUpdate
from .calculator import StopLossCalculator
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool


class StopLossManager:
    """Manager for automatic stop loss updates."""

    def __init__(
            self,
            market_data: MarketDataTool,
            orders: OrdersTool,
            config: Optional[StopLossConfig] = None,
            enabled: bool = True
    ):
        """Initialize the stop loss manager."""
        self.market_data = market_data
        self.orders = orders
        self.config = config or StopLossConfig()
        self.calculator = StopLossCalculator(self.config)
        self.enabled = enabled

        logfire.info("Stop loss manager initialized",
                     enabled=enabled,
                     **self.config.model_dump())

    def update_position_stops(self, symbol: str) -> Dict[str, Any]:
        """Update stop losses for all positions in the given symbol."""
        if not self.enabled:
            logfire.info("Stop loss manager disabled, skipping updates", symbol=symbol)
            return {"symbol": symbol, "updates": [], "errors": []}

        results = {
            "symbol": symbol,
            "updates": [],
            "errors": []
        }

        try:
            with logfire.span("position_stops_update") as span:
                span.set_attribute("symbol", symbol)

                positions = self.orders.get_positions(symbol)
                if not positions:
                    logfire.info("No positions found", symbol=symbol)
                    return results

                current_price = self.market_data.get_current_price(symbol)
                historical_data = self.market_data.fetch_historical_data(
                    symbol,
                    self.config.timeframe
                )

                atr_value = self.calculator.calculate_atr(historical_data)

                for position in positions:
                    try:
                        with logfire.span("process_position") as pos_span:
                            pos_span.set_attribute("position", position)

                            update = self.calculator.calculate_stop_loss(
                                symbol=symbol,
                                current_price=current_price,
                                entry_price=position.entry_price,  # Accesso diretto all'attributo
                                position_size=position.size,  # Accesso diretto all'attributo
                                position_type=position.side.lower(),  # Accesso diretto all'attributo
                                atr_value=atr_value,
                                previous_stop_loss=position.stop_loss  # Accesso diretto all'attributo
                            )

                            if (update.previous_stop_loss and
                                    update.new_stop_loss == update.previous_stop_loss):
                                logfire.info("Stop loss unchanged", **update.model_dump())
                                continue

                            result = self.orders.set_trading_stops(
                                symbol=symbol,
                                stopLoss=str(update.new_stop_loss)
                            )

                            logfire.info("Stop loss updated successfully",
                                         update=update.model_dump(),
                                         result=result)

                            # Use appropriate attribute for position identification
                            position_id = getattr(position, 'position_idx', position.symbol)

                            results["updates"].append({
                                "position_id": position_id,
                                "update": update.model_dump(),
                                "result": result
                            })

                    except Exception as e:
                        # Use appropriate attribute for position identification
                        position_id = getattr(position, 'position_idx', position.symbol)
                        error_details = {
                            "position_id": position_id,
                            "error": str(e)
                        }
                        logfire.error("Position update failed", **error_details)
                        results["errors"].append(error_details)

                logfire.info("Position stops update completed",
                             symbol=symbol,
                             successful_updates=len(results["updates"]),
                             failed_updates=len(results["errors"]))

                return results

        except Exception as e:
            logfire.error("Position stops update failed",
                          symbol=symbol,
                          error=str(e))
            raise

    def monitor_positions(
            self,
            symbols: List[str],
            interval_seconds: int = 60
    ) -> None:
        """Monitor positions and update stop losses periodically."""
        if not self.enabled:
            logfire.info("Stop loss manager disabled, monitoring stopped")
            return

        logfire.info("Starting position monitor",
                     symbols=symbols,
                     interval=interval_seconds)

        while True:
            try:
                for symbol in symbols:
                    with logfire.span("monitor_symbol") as span:
                        span.set_attribute("symbol", symbol)
                        self.update_position_stops(symbol)

                time.sleep(interval_seconds)

            except Exception as e:
                logfire.error("Position monitoring error",
                              symbols=symbols,
                              error=str(e))
                time.sleep(5)