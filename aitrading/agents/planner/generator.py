import os
from typing import Dict, Any, Tuple
from jinja2 import Template
import logfire

from ...models import (
    TradingParameters, TradingPlan, ExistingOrder,
    PlannedOrder, StrategicContext
)
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator, TimeframeVolatility
from ...tools.redis.order_context import OrderContext
from .analysis import MarketAnalyzer
from .base import BaseAIClient
from datetime import datetime, UTC


def _convert_pydantic_to_dict(obj: Any) -> Any:
    """Convert Pydantic objects to plain dictionaries recursively."""
    # Special case for TimeframeVolatility: pass it through unchanged
    if isinstance(obj, TimeframeVolatility):
        return obj

    if hasattr(obj, 'model_dump'):
        obj_dict = obj.model_dump()
    elif hasattr(obj, 'dict'):
        obj_dict = obj.dict()
    else:
        return obj

    for key, value in obj_dict.items():
        if isinstance(value, TimeframeVolatility):
            obj_dict[key] = value
        elif hasattr(value, 'model_dump') or hasattr(value, 'dict'):
            obj_dict[key] = _convert_pydantic_to_dict(value)
        elif isinstance(value, dict):
            obj_dict[key] = {k: _convert_pydantic_to_dict(v) for k, v in value.items()}
        elif isinstance(value, list):
            obj_dict[key] = [_convert_pydantic_to_dict(item) for item in value]
        elif isinstance(value, (int, float, str, bool, type(None))):
            obj_dict[key] = value
        else:
            obj_dict[key] = str(value)
    return obj_dict


class PlanGenerator:
    """Handles the generation of trading plans using market analysis and AI."""

    def __init__(self,
                 market_data: MarketDataTool,
                 orders: OrdersTool,
                 chart_generator: ChartGeneratorTool,
                 volatility_calculator: VolatilityCalculator,
                 order_context: OrderContext,
                 ai_client: BaseAIClient,
                 system_template: Template):
        """Initialize the plan generator."""
        self.market_analyzer = MarketAnalyzer(
            market_data=market_data,
            chart_generator=chart_generator,
            volatility_calculator=volatility_calculator
        )
        self.orders = orders
        self.ai_client = ai_client
        self.system_template = system_template
        self.order_context = order_context

    def generate(self, params: TradingParameters) -> TradingPlan:
        """Generate a complete trading plan."""
        try:
            with logfire.span("generate_trading_plan") as span:
                span.set_attributes({
                    "symbol": params.symbol,
                    "budget": params.budget,
                    "leverage": params.leverage,
                })

                # Get market analysis
                market_data = self._analyze_market(params.symbol)

                # Get current positions and orders
                positions_orders = self._fetch_positions_orders(params.symbol)

                # Calculate allocated budgets
                positions_budget, orders_budget = self._calculate_allocated_budget(
                    positions_orders["current_positions"],
                    positions_orders["existing_orders"],
                    market_data["current_price"]
                )

                # Generate template variables
                template_vars = self._prepare_template_vars(
                    params=params,
                    market_data=market_data,
                    positions_orders=positions_orders,
                    positions_budget=positions_budget,
                    orders_budget=orders_budget
                )

                # Generate system prompt
                system_prompt = self.system_template.render(**template_vars)

                if "RENDERED_PROMPT_FILE" in os.environ:
                    with open(os.environ['RENDERED_PROMPT_FILE'].replace('symbol', params.symbol), 'w') as f:
                        f.write(system_prompt)

                # Get AI response
                plan_data = self._get_ai_response(
                    system_prompt=system_prompt,
                    charts=market_data["charts"]
                )

                # Create and validate trading plan
                trading_plan = self._create_trading_plan(
                    plan_data=plan_data,
                    params=params
                )

                logfire.info("Trading plan generated", symbol=params.symbol)
                return trading_plan

        except Exception as e:
            logfire.exception("Plan generation failed", error=str(e))
            raise Exception(f"Error generating trading plan: {str(e)}")

    def _analyze_market(self, symbol: str) -> Dict[str, Any]:
        """Get complete market analysis including charts."""
        with logfire.span("market_analysis"):
            return self.market_analyzer.analyze_market(symbol)

    def _fetch_positions_orders(self, symbol: str) -> Dict[str, Any]:
        """Fetch current positions and orders with their strategic context."""
        positions = []
        existing_orders = []

        try:
            with logfire.span("fetch_positions_orders"):
                # Get current positions
                positions = self.orders.get_positions(symbol)
                logfire.info("Current positions fetched", count=len(positions))

                # Get active orders
                raw_orders = self.orders.get_active_orders(symbol)

                # Fetch strategic context for each order
                for order in raw_orders:
                    try:
                        context_data = self.order_context.get_context(order.order_link_id)
                        if context_data and "data" in context_data:
                            # Create StrategicContext from saved data
                            strategic_context = StrategicContext(**context_data["data"])
                            order.strategic_context = strategic_context

                            logfire.debug("Loaded strategic context",
                                          order_link_id=order.order_link_id,
                                          context=context_data)
                        else:
                            logfire.debug("No strategic context found",
                                          order_link_id=order.order_link_id)

                    except Exception as e:
                        logfire.error("Failed to load strategic context",
                                      order_link_id=order.order_link_id,
                                      error=str(e))

                existing_orders = raw_orders
                logfire.info("Active orders fetched",
                             count=len(existing_orders),
                             with_context=sum(1 for o in existing_orders if hasattr(o, 'strategic_context')))

        except Exception as e:
            logfire.error("Failed to fetch positions/orders", error=str(e))

        return {
            "current_positions": positions,
            "existing_orders": existing_orders
        }

    def _prepare_template_vars(self,
                               params: TradingParameters,
                               market_data: Dict,
                               positions_orders: Dict,
                               positions_budget: float,
                               orders_budget: float) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        from ...models import generate_uuid_short

        # Generate unique IDs for this plan
        plan_id = generate_uuid_short(8)
        session_id = generate_uuid_short(4)

        # Get volatility metrics - keep TimeframeVolatility object intact
        volatility_metrics = market_data.get("volatility_metrics")

        if isinstance(volatility_metrics, TimeframeVolatility):
            # Log detailed metrics for debugging without converting to dict
            for timeframe, metrics in volatility_metrics.metrics.items():
                logfire.info(f"Volatility metrics for {timeframe}",
                             timeframe=timeframe,
                             direction_score=metrics.direction_score,
                             opportunity_score=metrics.opportunity_score,
                             regime=metrics.regime,
                             atr=metrics.atr,
                             atr_percentile=metrics.atr_percentile)

        # Convert existing orders to plain dicts
        existing_orders = [_convert_pydantic_to_dict(order)
                           for order in positions_orders["existing_orders"]]

        template_vars = {
            "plan_id": plan_id,
            "session_id": session_id,
            "current_price": market_data["current_price"],
            "symbol": params.symbol,
            "total_budget": params.budget,
            "leverage": params.leverage,
            "positions_budget": positions_budget,
            "orders_budget": orders_budget,
            "existing_orders": existing_orders,
            "current_positions": positions_orders["current_positions"],
            "atr_timeframe": params.stop_loss_config.get("timeframe") if params.stop_loss_config else "1H",
            "volatility_metrics": volatility_metrics,
            "current_datetime": datetime.now(UTC).isoformat(),
        }

        logfire.info("Template variables prepared", template_vars=template_vars)

        return template_vars

    def _get_ai_response(self, system_prompt: str, charts: list) -> Dict[str, Any]:
        """Get response from AI provider."""
        with logfire.span("generate_strategy") as span:
            span.set_attributes({
                "ai_provider": self.ai_client.__class__.__name__,
                "charts_count": len(charts)
            })

            response_dict = self.ai_client.generate_strategy(system_prompt, charts)

            if 'plan' not in response_dict:
                raise ValueError("AI response missing plan data")

            return response_dict['plan']

    def _create_trading_plan(self, plan_data: Dict, params: TradingParameters) -> TradingPlan:
        """Create and validate trading plan from AI response."""
        try:
            # Create trading plan using only the fields we need
            trading_plan = TradingPlan(
                id=plan_data['id'],
                session_id=plan_data['session_id'],
                parameters=params,
                orders=plan_data.get('orders', []),
                cancellations=plan_data.get('cancellations'),
                analysis=plan_data['analysis']
            )

            # Save strategic context for each new order
            for order in trading_plan.orders:
                if hasattr(order, 'strategic_context'):
                    success = self.order_context.save_context(
                        order_link_id=order.order_link_id,
                        context=order.strategic_context
                    )
                    if not success:
                        logfire.warning("Failed to save strategic context",
                                        order_link_id=order.order_link_id)

            # Add tags for logging
            tags = ["plan", params.symbol]
            if trading_plan.orders and len(trading_plan.orders):
                tags.append("orders")
            if trading_plan.cancellations and len(trading_plan.cancellations):
                tags.append("cancellations")

            logfire.info("Trading plan created", _tags=tags, **_convert_pydantic_to_dict(trading_plan))
            return trading_plan

        except Exception as e:
            logfire.error("Failed to create trading plan", error=str(e))
            raise

    def _calculate_positions_budget(self, positions: list, current_price: float) -> float:
        """Calculate total budget allocated in open positions."""
        total_budget = 0.0
        for position in positions:
            try:
                if isinstance(position, dict):
                    # Legacy dictionary format
                    position_size = float(position["size"])
                    entry_price = float(position["entry_price"])
                    leverage = float(position["leverage"])
                else:
                    # New Position object
                    position_size = position.size
                    entry_price = position.entry_price
                    leverage = position.leverage

                # Calculate actual budget (position value / leverage)
                position_value = position_size * entry_price
                position_budget = position_value / leverage
                total_budget += position_budget

                logfire.debug("Position budget calculation",
                              size=position_size,
                              entry_price=entry_price,
                              leverage=leverage,
                              position_value=position_value,
                              position_budget=position_budget,
                              age_hours=getattr(position, 'age_hours', None),
                              is_in_profit=getattr(position, 'is_in_profit', lambda: None)())

            except Exception as e:
                logfire.error("Error calculating position budget",
                              error=str(e),
                              position=str(position))
                continue

        return total_budget

    def _calculate_orders_budget(self, orders: list) -> float:
        """Calculate total budget allocated in pending orders."""
        total_budget = 0.0
        for order in orders:
            try:
                # Per gli oggetti ExistingOrder dobbiamo usare accesso agli attributi
                if isinstance(order, ExistingOrder):
                    # For market orders use qty directly
                    qty = float(order.qty)
                    price = float(order.price) if order.price is not None else 0
                    # Nota: ExistingOrder potrebbe non avere leverage, usiamo 1 come default
                    leverage = 1  # Default leverage if not available
                    order_budget = (qty * price) / leverage if price > 0 else 0
                else:
                    # For limit orders use price * qty
                    qty = float(order["qty"])
                    price = float(order["price"]) if order["price"] is not None else 0
                    leverage = float(order.get("leverage", 1))  # Default to 1 if not present
                    order_budget = (qty * price) / leverage if price > 0 else 0

                total_budget += order_budget

                logfire.debug("Order budget calculation",
                              type=order.type if isinstance(order, ExistingOrder) else order.get("type"),
                              qty=qty,
                              price=price,
                              leverage=leverage,
                              order_budget=order_budget,
                              age_hours=getattr(order, 'age_hours', None))

            except Exception as e:
                logfire.error("Error calculating order budget",
                              error=str(e),
                              order=str(order))
                continue

        return total_budget

    def _calculate_allocated_budget(self, positions: list, orders: list, current_price: float) -> Tuple[float, float]:
        """Calculate total allocated budget and breakdown by positions and orders."""
        positions_budget = self._calculate_positions_budget(positions, current_price)
        orders_budget = self._calculate_orders_budget(orders)

        logfire.info("Budget allocation calculated",
                     positions_budget=positions_budget,
                     orders_budget=orders_budget,
                     total_allocated=positions_budget + orders_budget)

        return positions_budget, orders_budget