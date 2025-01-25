from typing import Dict, List, Any, Optional
import asyncio
import logfire

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
        config: Optional[StopLossConfig] = None
    ):
        """Initialize the stop loss manager.
        
        Args:
            market_data: Market data tool instance
            orders: Orders tool instance
            config: Optional stop loss configuration
        """
        self.market_data = market_data
        self.orders = orders
        self.config = config or StopLossConfig()
        self.calculator = StopLossCalculator(self.config)
        
        logfire.info("Stop loss manager initialized", **self.config.model_dump())

    async def update_position_stops(self, symbol: str) -> Dict[str, Any]:
        """Update stop losses for all positions in the given symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dictionary containing:
            - updates: List of successful updates
            - errors: List of failed updates
        """
        results = {
            "symbol": symbol,
            "updates": [],
            "errors": []
        }
        
        try:
            with logfire.span("position_stops_update") as span:
                span.set_attribute("symbol", symbol)
                
                # Get current positions
                positions = self.orders.get_positions(symbol)
                if not positions:
                    logfire.info("No positions found", symbol=symbol)
                    return results

                # Get current market data
                current_price = self.market_data.get_current_price(symbol)
                historical_data = self.market_data.fetch_historical_data(
                    symbol, 
                    self.config.timeframe
                )

                # Calculate current ATR
                atr_value = self.calculator.calculate_atr(historical_data)

                # Process each position
                for position in positions:
                    try:
                        with logfire.span("process_position") as pos_span:
                            pos_span.set_attribute("position_id", position["id"])
                            
                            # Calculate new stop loss
                            update = self.calculator.calculate_stop_loss(
                                symbol=symbol,
                                current_price=current_price,
                                entry_price=float(position["entry_price"]),
                                position_size=float(position["size"]),
                                position_type=position["side"].lower(),
                                atr_value=atr_value,
                                previous_stop_loss=position.get("stop_loss")
                            )

                            # Skip update if stop loss hasn't changed
                            if (update.previous_stop_loss and 
                                update.new_stop_loss == update.previous_stop_loss):
                                logfire.info("Stop loss unchanged", **update.model_dump())
                                continue

                            # Apply new stop loss
                            result = self.orders.set_trading_stops(
                                symbol=symbol,
                                stopLoss=str(update.new_stop_loss)
                            )

                            logfire.info("Stop loss updated successfully", 
                                       update=update.model_dump(),
                                       result=result)
                            
                            results["updates"].append({
                                "position_id": position["id"],
                                "update": update.model_dump(),
                                "result": result
                            })

                    except Exception as e:
                        error_details = {
                            "position_id": position["id"],
                            "error": str(e)
                        }
                        logfire.error("Position update failed", **error_details)
                        results["errors"].append(error_details)

                # Log final results
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

    async def monitor_positions(
        self,
        symbols: List[str],
        interval_seconds: int = 60
    ) -> None:
        """Monitor positions and update stop losses periodically.
        
        Args:
            symbols: List of trading pair symbols to monitor
            interval_seconds: Update interval in seconds (default 60)
        """
        logfire.info("Starting position monitor",
                    symbols=symbols,
                    interval=interval_seconds)
        
        while True:
            try:
                for symbol in symbols:
                    with logfire.span("monitor_symbol") as span:
                        span.set_attribute("symbol", symbol)
                        await self.update_position_stops(symbol)

                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logfire.error("Position monitoring error",
                            symbols=symbols,
                            error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry