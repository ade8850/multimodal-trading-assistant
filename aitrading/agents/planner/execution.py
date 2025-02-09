from typing import Dict, List
import time
import logfire

from ...models import TradingPlan, OrderCancellation, ChildOrder, OrderRole
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
                    results["orders"] = self._execute_orders_with_children(plan)

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

    def _execute_orders_with_children(self, plan: TradingPlan) -> List[Dict]:
        """Execute parent orders and their associated child orders."""
        results = []

        for order in plan.orders:
            try:
                with logfire.span("execute_order_group") as span:
                    span.set_attributes({
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "symbol": order.symbol,
                        "type": order.type,
                        "child_orders_count": len(order.child_orders)
                    })

                    # Configure position settings first
                    logfire.info("Configuring position settings",
                                 symbol=order.symbol,
                                 leverage=order.order.entry.leverage)

                    self.orders.set_position_settings(
                        symbol=order.symbol,
                        leverage=order.order.entry.leverage
                    )

                    # Place main entry order
                    logfire.info("Placing main order",
                                 order_id=order.id,
                                 order_link_id=order.order_link_id,
                                 symbol=order.symbol,
                                 type=order.type)

                    entry_result = self.orders.place_strategy_orders(order)

                    if entry_result.get("errors"):
                        raise ValueError(f"Entry order execution failed: {entry_result['errors']}")

                    main_order_result = {
                        "order_id": order.id,
                        "order_link_id": order.order_link_id,
                        "result": entry_result,
                        "child_orders": []
                    }

                    # Get the exchange-assigned order ID for parent reference
                    parent_order_id = entry_result.get("entry", {}).get("result", {}).get("orderId")

                    if parent_order_id:
                        # Place child orders (TP/SL)
                        child_results = self._execute_child_orders(
                            order.child_orders,
                            parent_order_id,
                            order.order_link_id,
                            order.symbol
                        )
                        main_order_result["child_orders"] = child_results

                        logfire.info("Order group execution completed",
                                     parent_order_id=parent_order_id,
                                     successful_children=sum(1 for c in child_results if "error" not in c),
                                     failed_children=sum(1 for c in child_results if "error" in c))
                    else:
                        logfire.warning("No parent order ID received, skipping child orders")

                    results.append(main_order_result)

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

    def _execute_child_orders(
            self,
            child_orders: List[ChildOrder],
            parent_order_id: str,
            parent_link_id: str,
            symbol: str
    ) -> List[Dict]:
        """Execute child orders (TP/SL) associated with a parent order."""
        results = []

        for child in child_orders:
            try:
                with logfire.span("execute_child_order") as span:
                    span.set_attributes({
                        "role": child.role,
                        "symbol": symbol,
                        "parent_order_id": parent_order_id
                    })

                    # Prepare child order parameters
                    params = {
                        "category": "linear",
                        "symbol": symbol,
                        "side": child.parameters.side,
                        "orderType": child.parameters.type.title(),
                        "qty": str(child.parameters.size),
                        "reduceOnly": True,
                        "closeOnTrigger": True,
                        "orderLinkId": f"{parent_link_id}-{child.role.value}"
                    }

                    # Add price for limit orders
                    if child.parameters.type == "limit" and child.parameters.price:
                        params["price"] = str(child.parameters.price)

                    # Add trigger price if specified
                    if child.parameters.trigger_price:
                        params["triggerPrice"] = str(child.parameters.trigger_price)

                    logfire.info("Placing child order",
                                 role=child.role,
                                 parent_id=parent_order_id,
                                 params=params)

                    response = self.orders.session.place_order(**params)

                    if response["retCode"] != 0:
                        raise ValueError(f"Child order placement failed: {response['retMsg']}")

                    results.append({
                        "role": child.role,
                        "order_link_id": params["orderLinkId"],
                        "result": response["result"]
                    })

                    logfire.info("Child order placed successfully",
                                 role=child.role,
                                 order_id=response["result"].get("orderId"))

            except Exception as e:
                logfire.error("Child order placement failed",
                              role=child.role,
                              parent_id=parent_order_id,
                              error=str(e))

                results.append({
                    "role": child.role,
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