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

                logfire.info("Starting plan execution", 
                           plan_id=plan.id,
                           symbol=plan.parameters.symbol,
                           budget=plan.parameters.budget,
                           leverage=plan.parameters.leverage)

                results = {
                    "plan_id": plan.id,
                    "cancellations": [],
                    "orders": [],
                }

                # Initialize components
                stop_loss_manager = self._init_stop_loss_manager(plan) if plan.parameters.stop_loss_config else None
                if stop_loss_manager:
                    logfire.info("Stop loss manager initialized",
                               symbol=plan.parameters.symbol,
                               config=plan.parameters.stop_loss_config)
                else:
                    logfire.info("No stop loss configuration provided")

                # Execute plan steps in sequence
                if plan.cancellations:
                    logfire.info("Processing order cancellations",
                               count=len(plan.cancellations))
                    results["cancellations"] = self._execute_cancellations(plan.cancellations)
                    time.sleep(1)  # Brief pause after cancellations

                if plan.orders:
                    logfire.info("Processing new orders",
                               count=len(plan.orders))
                    results["orders"] = self._execute_orders(plan)

                if stop_loss_manager:
                    logfire.info("Updating stop losses",
                               symbol=plan.parameters.symbol)
                    results["stop_loss_updates"] = self._update_stop_losses(
                        stop_loss_manager, 
                        plan.parameters.symbol
                    )

                # Log execution summary
                success_metrics = {
                    "successful_cancellations": sum(1 for c in results["cancellations"] if c.get("status") == "success"),
                    "failed_cancellations": sum(1 for c in results["cancellations"] if c.get("status") != "success"),
                    "successful_orders": sum(1 for o in results["orders"] if "error" not in o),
                    "failed_orders": sum(1 for o in results["orders"] if "error" in o),
                    "stop_loss_updates": len(results.get("stop_loss_updates", {}).get("updates", [])) if "stop_loss_updates" in results else 0,
                    "stop_loss_errors": len(results.get("stop_loss_updates", {}).get("errors", [])) if "stop_loss_updates" in results else 0
                }

                logfire.info("Plan execution completed", 
                           plan_id=plan.id,
                           symbol=plan.parameters.symbol,
                           **success_metrics)

                return results

        except Exception as e:
            logfire.exception("Plan execution failed", 
                          plan_id=plan.id,
                          symbol=plan.parameters.symbol,
                          error=str(e))
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
            logfire.error("Failed to initialize stop loss manager",
                       symbol=plan.parameters.symbol,
                       config=plan.parameters.stop_loss_config,
                       error=str(e))
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
                    
                    logfire.info("Cancelling order",
                               order_id=cancel.id,
                               order_link_id=cancel.order_link_id,
                               symbol=cancel.symbol,
                               reason=cancel.reason)

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

                    logfire.info("Order cancelled successfully",
                               order_id=cancel.id,
                               symbol=cancel.symbol,
                               order_link_id=cancel.order_link_id)

            except Exception as e:
                logfire.error("Order cancellation failed",
                           order_id=cancel.id,
                           order_link_id=cancel.order_link_id,
                           symbol=cancel.symbol,
                           error=str(e))
                
                results.append({
                    "order_id": cancel.id,
                    "order_link_id": cancel.order_link_id,
                    "error": str(e),
                    "status": "failed"
                })

        # Log summary
        success_count = sum(1 for r in results if r["status"] == "success")
        logfire.info("Cancellations execution completed",
                   total=len(cancellations),
                   successful=success_count,
                   failed=len(cancellations) - success_count)

        return results

    def _execute_orders(self, plan: TradingPlan) -> List[Dict]:
        """Execute new orders from the plan."""
        results = []
        for order in plan.orders:
            try:
                with logfire.span("execute_order") as span:
                    span.set_attributes({
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "symbol": order.symbol,
                        "type": order.type
                    })

                    # Configure position settings
                    logfire.info("Configuring position settings",
                               symbol=order.symbol,
                               leverage=order.order.entry.leverage)

                    self.orders.set_position_settings(
                        symbol=order.symbol,
                        leverage=order.order.entry.leverage
                    )

                    # Place the order
                    logfire.info("Placing order",
                               order_id=order.id,
                               order_link_id=order.order_link_id,
                               symbol=order.symbol,
                               type=order.type)

                    result = self.orders.place_strategy_orders(order)
                    if result.get("errors"):
                        raise ValueError(f"Order execution failed for {order.id}: {result['errors']}")

                    results.append({
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "result": result
                    })

                    logfire.info("Order placed successfully",
                               order_id=order.id,
                               order_link_id=order.order_link_id,
                               symbol=order.symbol,
                               type=order.type,
                               leverage=order.order.entry.leverage)

            except Exception as e:
                logfire.error("Order placement failed",
                           order_id=order.id,
                           order_link_id=order.order_link_id,
                           symbol=order.symbol,
                           type=order.type,
                           error=str(e))

                results.append({
                    "order_id": order.id,
                    "order_link_id": order.order_link_id,
                    "error": str(e)
                })

        # Log summary
        success_count = sum(1 for r in results if "error" not in r)
        logfire.info("Orders execution completed",
                   total=len(plan.orders),
                   successful=success_count,
                   failed=len(plan.orders) - success_count)

        return results

    def _update_stop_losses(self, stop_loss_manager: StopLossManager, symbol: str) -> Dict:
        """Update stop losses for active positions."""
        try:
            with logfire.span("update_stop_losses"):
                positions = self.orders.get_positions(symbol)
                if not positions:
                    logfire.info("No active positions to update stop losses",
                               symbol=symbol)
                    return {}

                logfire.info("Updating stop losses",
                           symbol=symbol,
                           positions_count=len(positions))

                stop_loss_results = stop_loss_manager.update_position_stops(symbol)
                
                # Log detailed results
                successful_updates = len(stop_loss_results.get("updates", []))
                failed_updates = len(stop_loss_results.get("errors", []))
                
                logfire.info("Stop loss updates completed",
                           symbol=symbol,
                           successful_updates=successful_updates,
                           failed_updates=failed_updates)

                return stop_loss_results

        except Exception as e:
            logfire.exception("Stop loss update failed",
                          symbol=symbol,
                          error=str(e))
            return {
                "error": str(e),
                "updates": [],
                "errors": [{
                    "error": str(e),
                    "symbol": symbol
                }]
            }