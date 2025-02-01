from typing import Dict, List
import time
import logfire

from ...models import TradingPlan, OrderCancellation
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool
from ...tools.stop_loss import StopLossManager, StopLossConfig

class PlanExecutor:
    """Handles the execution of trading plans including orders and stop losses."""

    def __init__(self, market_data: MarketDataTool, orders: OrdersTool):
        """Initialize the plan executor.
        
        Args:
            market_data: Service for market data operations
            orders: Service for order management
        """
        self.market_data = market_data
        self.orders = orders

    def execute(self, plan: TradingPlan) -> Dict:
        """Execute all operations in the trading plan.
        
        Args:
            plan: The trading plan to execute
            
        Returns:
            Dict containing execution results
        """
        try:
            with logfire.span("execute_trading_plan") as span:
                span.set_attributes({
                    "plan_id": plan.id,
                    "symbol": plan.parameters.symbol,
                    "orders_count": len(plan.orders),
                    "cancellations_count": len(plan.cancellations or [])
                })

                results = {
                    "plan_id": plan.id,
                    "cancellations": [],
                    "orders": [],
                }

                # Initialize components
                stop_loss_manager = self._init_stop_loss_manager(plan) if plan.parameters.stop_loss_config else None

                # Execute plan steps in sequence
                if plan.cancellations:
                    results["cancellations"] = self._execute_cancellations(plan.cancellations)
                    time.sleep(1)  # Brief pause after cancellations

                if plan.orders:
                    results["orders"] = self._execute_orders(plan)

                if stop_loss_manager:
                    results["stop_loss_updates"] = self._update_stop_losses(
                        stop_loss_manager, 
                        plan.parameters.symbol
                    )

                logfire.info("Plan execution complete", **{
                    "plan_id": plan.id,
                    "successful_cancellations": sum(1 for c in results["cancellations"] if c.get("status") == "success"),
                    "successful_orders": sum(1 for o in results["orders"] if "error" not in o),
                    "stop_loss_updated": "stop_loss_updates" in results
                })

                return results

        except Exception as e:
            logfire.exception("Plan execution failed", **{"error": str(e), "plan_id": plan.id})
            raise Exception(f"Error executing trading plan: {str(e)}")

    def _init_stop_loss_manager(self, plan: TradingPlan) -> StopLossManager:
        """Initialize the stop loss manager with configuration."""
        try:
            with logfire.span("init_stop_loss_manager"):
                stop_loss_config = StopLossConfig(**plan.parameters.stop_loss_config)
                manager = StopLossManager(
                    market_data=self.market_data,
                    orders=self.orders,
                    config=stop_loss_config
                )
                logfire.info("Stop loss manager initialized", **plan.parameters.stop_loss_config)
                return manager
        except Exception as e:
            logfire.error("Failed to initialize stop loss manager", error=str(e))
            return None

    def _execute_cancellations(self, cancellations: List[OrderCancellation]) -> List[Dict]:
        """Execute a list of order cancellations."""
        results = []
        for cancel in cancellations:
            try:
                with logfire.span("cancel_order") as span:
                    span.set_attributes({
                        "order_id": cancel.id,
                        "order_link_id": cancel.order_link_id,
                        "symbol": cancel.symbol
                    })
                    
                    result = self.orders.cancel_order(
                        symbol=cancel.symbol,
                        order_id=cancel.id,
                        order_link_id=cancel.order_link_id
                    )

                    results.append({
                        "order_id": cancel.id,
                        "order_link_id": cancel.order_link_id,
                        "result": result,
                        "status": "success"
                    })

                    logfire.info("Order cancelled", **{
                        "order_id": cancel.id,
                        "symbol": cancel.symbol,
                        "reason": cancel.reason
                    })

            except Exception as e:
                results.append({
                    "order_id": cancel.id,
                    "order_link_id": cancel.order_link_id,
                    "error": str(e),
                    "status": "failed"
                })
                logfire.error("Order cancellation failed", **{
                    "order_id": cancel.id,
                    "symbol": cancel.symbol,
                    "error": str(e)
                })

        return results

    def _execute_orders(self, plan: TradingPlan) -> List[Dict]:
        """Execute new orders from the plan."""
        results = []
        for order in plan.orders:
            try:
                with logfire.span("execute_order"):
                    # Configure position settings
                    self.orders.set_position_settings(
                        symbol=order.symbol,
                        leverage=order.order.entry.leverage
                    )

                    # Place the order
                    result = self.orders.place_strategy_orders(order)
                    if result.get("errors"):
                        raise ValueError(f"Order execution failed for {order.id}: {result['errors']}")

                    results.append({
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "result": result
                    })

                    logfire.info("Order placed", **{
                        "order_id": order.id,
                        "symbol": order.symbol,
                        "type": order.type,
                        "leverage": order.order.entry.leverage
                    })

            except Exception as e:
                results.append({
                    "order_id": order.id,
                    "order_link_id": order.order_link_id,
                    "error": str(e)
                })
                logfire.error("Order placement failed", **{
                    "order_id": order.id,
                    "symbol": order.symbol,
                    "error": str(e)
                })

        return results

    def _update_stop_losses(self, stop_loss_manager: StopLossManager, symbol: str) -> Dict:
        """Update stop losses for active positions."""
        try:
            with logfire.span("update_stop_losses"):
                positions = self.orders.get_positions(symbol)
                if not positions:
                    logfire.info("No active positions to update stop losses")
                    return {}

                stop_loss_results = stop_loss_manager.update_position_stops(symbol)
                logfire.info("Stop loss updates executed",
                           updates=len(stop_loss_results.get("updates", [])),
                           errors=len(stop_loss_results.get("errors", [])))
                return stop_loss_results

        except Exception as e:
            logfire.exception("Stop loss update failed", error=str(e))
            return {
                "error": str(e),
                "updates": [],
                "errors": [{"error": str(e)}]
            }