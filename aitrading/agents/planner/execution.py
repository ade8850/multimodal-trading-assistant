from typing import Dict, List
import time
import logfire

from ...models import TradingPlan, OrderCancellation, PlannedOrder
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
        """Execute all operations in the trading plan."""
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

                # Execute plan steps in sequence
                if plan.cancellations:
                    logfire.info("Processing order cancellations",
                                 count=len(plan.cancellations))
                    results["cancellations"] = self._execute_cancellations(plan.cancellations)
                    time.sleep(1)  # Brief pause after cancellations

                if plan.orders:
                    logfire.info("Processing orders",
                                 count=len(plan.orders))
                    results["orders"] = self._execute_orders(plan)

                # Log execution summary
                success_metrics = {
                    "successful_cancellations": sum(
                        1 for c in results["cancellations"] if c.get("status") == "success"),
                    "failed_cancellations": sum(1 for c in results["cancellations"] if c.get("status") != "success"),
                    "successful_orders": sum(1 for o in results["orders"] if "error" not in o),
                    "failed_orders": sum(1 for o in results["orders"] if "error" in o),
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

    def _execute_orders(self, plan: TradingPlan) -> List[Dict]:
        """Execute order operations."""
        results = []
        for order in plan.orders:
            try:
                with logfire.span("execute_order") as span:
                    span.set_attributes({
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "symbol": order.symbol
                    })

                    # Configura impostazioni posizione
                    logfire.info("Configuring position settings",
                                 symbol=order.symbol,
                                 leverage=order.order.entry.leverage)

                    self.orders.set_position_settings(
                        symbol=order.symbol,
                        leverage=order.order.entry.leverage
                    )

                    # Convert order to dictionary and ensure reduce_only is present
                    order_data = order.model_dump()
                    order_data["reduce_only"] = order_data.get("reduce_only", False)

                    # Recreate order with reduce_only field
                    order = PlannedOrder.model_validate(order_data)

                    logfire.info("Placing order",
                                 order_id=order.id,
                                 order_link_id=order.order_link_id,
                                 symbol=order.symbol,
                                 type=order.type,
                                 reduce_only=order_data["reduce_only"])

                    # Place order
                    entry_result = self.orders.place_strategy_orders(order)

                    if entry_result.get("errors"):
                        raise ValueError(f"Order execution failed: {entry_result['errors']}")

                    order_result = {
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "result": entry_result
                    }

                    results.append(order_result)

            except Exception as e:
                logfire.error("Order execution failed",
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

        return results

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

        success_count = sum(1 for r in results if r["status"] == "success")
        logfire.info("Cancellations execution completed",
                     total=len(cancellations),
                     successful=success_count,
                     failed=len(cancellations) - success_count)

        return results