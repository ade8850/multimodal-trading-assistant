import math
import os
from typing import Dict, Any, Tuple, List
from jinja2 import Template
import logfire

from ...models import (
    TradingParameters, TradingPlan, ExistingOrder,
    PlannedOrder, StrategicContext
)
from ...models.orders import OrderRole
from ...models.position import Position
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

    def _process_existing_orders(self, orders: List[ExistingOrder]) -> List[Dict[str, Any]]:
        """Process existing orders and their strategic context."""
        try:
            processed_orders = []
            for order in orders:
                try:
                    # Convert order to dict
                    order_dict = _convert_pydantic_to_dict(order)

                    # Load and process strategic context
                    context_data = self.order_context.get_context(order.order_link_id)
                    if context_data and "data" in context_data:
                        context = StrategicContext(**context_data["data"])
                        order_dict["strategic_context"] = _convert_pydantic_to_dict(context)

                        # Load child order contexts if this is a parent order
                        if hasattr(order, 'child_orders') and order.child_orders:
                            child_contexts = []
                            for child in order.child_orders:
                                child_link_id = f"{order.order_link_id}-{child.role.value}"
                                child_context = self.order_context.get_context(child_link_id)
                                if child_context and "data" in child_context:
                                    child_contexts.append({
                                        "role": child.role.value,
                                        "context": child_context["data"]
                                    })
                            order_dict["child_contexts"] = child_contexts

                    processed_orders.append(order_dict)

                except Exception as e:
                    logfire.error("Failed to process order",
                                  order_id=order.id,
                                  order_link_id=order.order_link_id,
                                  error=str(e))
                    continue

            return processed_orders

        except Exception as e:
            logfire.exception("Failed to process existing orders", error=str(e))
            raise

    def _calculate_position_limits(self, positions: List[Position]) -> Dict[str, float]:
        """Calculate position-based limits for reduce-only orders."""
        try:
            limits = {
                "max_long_reduce": 0.0,
                "max_short_reduce": 0.0,
                "total_long_size": 0.0,
                "total_short_size": 0.0
            }

            for position in positions:
                position_size = float(position.size)
                if position.side.lower() == "buy":
                    limits["total_long_size"] += position_size
                    limits["max_long_reduce"] = max(limits["max_long_reduce"], position_size)
                else:
                    limits["total_short_size"] += position_size
                    limits["max_short_reduce"] = max(limits["max_short_reduce"], position_size)

            logfire.info("Position limits calculated", limits=limits)
            return limits

        except Exception as e:
            logfire.exception("Failed to calculate position limits", error=str(e))
            raise

    def _prepare_template_vars(self,
                               params: TradingParameters,
                               market_data: Dict,
                               positions_orders: Dict,
                               positions_budget: float,
                               orders_budget: float) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        from ...models import generate_uuid_short

        try:
            with logfire.span("prepare_template_variables") as span:
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

                # Process existing orders with strategic context
                existing_orders = self._process_existing_orders(positions_orders["existing_orders"])

                # Calculate position-based limits
                position_limits = self._calculate_position_limits(positions_orders["current_positions"])

                # Calculate available budget considering reduce-only orders
                available_budget = self._calculate_available_budget(
                    total_budget=params.budget,
                    positions_budget=positions_budget,
                    orders_budget=orders_budget,
                    position_limits=position_limits
                )

                template_vars = {
                    "plan_id": plan_id,
                    "session_id": session_id,
                    "current_price": market_data["current_price"],
                    "symbol": params.symbol,
                    "total_budget": params.budget,
                    "leverage": params.leverage,
                    "positions_budget": positions_budget,
                    "orders_budget": orders_budget,
                    "available_budget": available_budget,
                    "existing_orders": existing_orders,
                    "current_positions": positions_orders["current_positions"],
                    "position_limits": position_limits,
                    "atr_timeframe": params.stop_loss_config.get("timeframe") if params.stop_loss_config else "1H",
                    "volatility_metrics": volatility_metrics,
                    "current_datetime": datetime.now(UTC).isoformat(),
                }

                logfire.info("Template variables prepared",
                             template_vars=_convert_pydantic_to_dict(template_vars))

                return template_vars

        except Exception as e:
            logfire.exception("Failed to prepare template variables", error=str(e))
            raise

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


    def _validate_exit_strategies(self, orders: List[PlannedOrder]) -> None:
        """Validate exit strategies for all orders."""
        try:
            for order in orders:
                if not order.order.exit:
                    raise ValueError(f"Order {order.id} missing exit strategy")

                # Validate take profit levels
                total_tp_size = sum(level.size_percentage for level in order.order.exit.take_profit)
                if not 0 < total_tp_size <= 100:
                    raise ValueError(f"Invalid total take profit size: {total_tp_size}%")

                # Validate stop loss levels
                total_sl_size = sum(level.size_percentage for level in order.order.exit.stop_loss)
                if not 0 < total_sl_size <= 100:
                    raise ValueError(f"Invalid total stop loss size: {total_sl_size}%")

                # Validate child orders match exit strategy
                if order.child_orders:
                    self._validate_child_orders_match_strategy(order)

                logfire.info("Exit strategy validated",
                             order_id=order.id,
                             tp_levels=len(order.order.exit.take_profit),
                             sl_levels=len(order.order.exit.stop_loss))

        except Exception as e:
            logfire.error("Exit strategy validation failed", error=str(e))
            raise

    def _validate_child_orders_match_strategy(self, order: PlannedOrder) -> None:
        """Validate child orders match the defined exit strategy."""
        try:
            # Group child orders by role
            tp_orders = [c for c in order.child_orders if c.role == OrderRole.PROFIT]
            sl_orders = [c for c in order.child_orders if c.role == OrderRole.PROTECT]

            # Validate take profit orders
            if len(tp_orders) != len(order.order.exit.take_profit):
                raise ValueError("Mismatch between take profit levels and orders")

            for tp_level, tp_order in zip(order.order.exit.take_profit, tp_orders):
                if not math.isclose(tp_level.size_percentage, tp_order.parameters.size_percentage, rel_tol=1e-9):
                    raise ValueError(
                        f"Take profit size mismatch: {tp_level.size_percentage}% vs {tp_order.parameters.size_percentage}%")

            # Validate stop loss orders
            if len(sl_orders) != len(order.order.exit.stop_loss):
                raise ValueError("Mismatch between stop loss levels and orders")

            for sl_level, sl_order in zip(order.order.exit.stop_loss, sl_orders):
                if not math.isclose(sl_level.size_percentage, sl_order.parameters.size_percentage, rel_tol=1e-9):
                    raise ValueError(
                        f"Stop loss size mismatch: {sl_level.size_percentage}% vs {sl_order.parameters.size_percentage}%")

            logfire.info("Child orders match strategy",
                         order_id=order.id,
                         tp_orders=len(tp_orders),
                         sl_orders=len(sl_orders))

        except Exception as e:
            logfire.error("Child order validation failed", error=str(e))
            raise

    def _derive_child_context(self, parent_context: StrategicContext, role: OrderRole) -> StrategicContext:
        """Derive strategic context for child orders based on parent context and role."""
        try:
            if role == OrderRole.PROTECT:
                rationale = f"Protection order based on parent setup: {parent_context.setup_rationale}"
                conditions = parent_context.invalidation_conditions
            elif role == OrderRole.PROFIT:
                rationale = f"Profit taking order based on parent setup: {parent_context.setup_rationale}"
                conditions = [f"Price reaches target level"]
            else:
                rationale = f"Exit order based on parent setup: {parent_context.setup_rationale}"
                conditions = parent_context.invalidation_conditions + ["Price reaches target level"]

            return StrategicContext(
                setup_rationale=rationale,
                market_bias=parent_context.market_bias,
                key_levels=parent_context.key_levels,
                catalysts=parent_context.catalysts,
                invalidation_conditions=conditions
            )

        except Exception as e:
            logfire.error("Failed to derive child context", error=str(e))
            raise
    def _validate_order_relationships(self, orders: List[PlannedOrder]) -> None:
        """Validate relationships between parent and child orders."""
        try:
            for order in orders:
                if not hasattr(order, 'child_orders') or not order.child_orders:
                    logfire.warning("Order missing child orders for exit strategy",
                                    order_id=order.id,
                                    order_link_id=order.order_link_id)
                    continue

                # Track total exit size
                total_exit_size = 0.0
                has_protection = False
                has_profit = False

                for child in order.child_orders:
                    # Validate child order properties
                    if not child.parameters.reduce_only:
                        raise ValueError(f"Child order {child.role} must be reduce-only")

                    if not 0 < child.parameters.size_percentage <= 100:
                        raise ValueError(
                            f"Invalid size percentage for {child.role}: {child.parameters.size_percentage}")

                    total_exit_size += child.parameters.size_percentage

                    # Track order roles
                    if child.role == OrderRole.PROTECT:
                        has_protection = True
                    elif child.role == OrderRole.PROFIT:
                        has_profit = True

                # Validate total exit size
                if not math.isclose(total_exit_size, 100.0, rel_tol=1e-9):
                    raise ValueError(f"Total exit size must be 100%, got {total_exit_size}%")

                # Validate required order types
                if not has_protection:
                    raise ValueError("Missing protection (stop loss) orders")
                if not has_profit:
                    raise ValueError("Missing profit taking orders")

                logfire.info("Order relationships validated",
                             order_id=order.id,
                             child_count=len(order.child_orders),
                             total_exit_size=total_exit_size)

        except Exception as e:
            logfire.error("Order relationship validation failed", error=str(e))
            raise

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

            # Validate order relationships and exit strategies
            if trading_plan.orders:
                self._validate_order_relationships(trading_plan.orders)
                self._validate_exit_strategies(trading_plan.orders)

            # Save strategic context for each new order and its children
            for order in trading_plan.orders:
                if hasattr(order, 'strategic_context'):
                    success = self.order_context.save_context(
                        order_link_id=order.order_link_id,
                        context=order.strategic_context
                    )
                    if not success:
                        logfire.warning("Failed to save strategic context",
                                        order_link_id=order.order_link_id)

                    # Save context for child orders
                    if hasattr(order, 'child_orders'):
                        for child in order.child_orders:
                            child_context = self._derive_child_context(
                                order.strategic_context,
                                child.role
                            )
                            child_link_id = f"{order.order_link_id}-{child.role.value}"
                            success = self.order_context.save_context(
                                order_link_id=child_link_id,
                                context=child_context
                            )
                            if not success:
                                logfire.warning("Failed to save child order context",
                                                parent_id=order.order_link_id,
                                                child_role=child.role)

            # Add tags for logging
            tags = ["plan", params.symbol]
            if trading_plan.orders and len(trading_plan.orders):
                tags.append("orders")
                if any(order.child_orders for order in trading_plan.orders):
                    tags.append("child_orders")
            if trading_plan.cancellations and len(trading_plan.cancellations):
                tags.append("cancellations")

            logfire.info("Trading plan created",
                         _tags=tags,
                         **_convert_pydantic_to_dict(trading_plan))
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

    def _calculate_available_budget(self,
                                    total_budget: float,
                                    positions_budget: float,
                                    orders_budget: float,
                                    position_limits: Dict[str, float]) -> Dict[str, float]:
        """Calculate available budget considering reduce-only orders."""
        try:
            # Calculate standard available budget
            base_available = total_budget - positions_budget - orders_budget

            # Calculate available for reduce-only orders based on position sizes
            available = {
                "standard": max(0.0, base_available),
                "reduce_only_long": position_limits["max_long_reduce"],
                "reduce_only_short": position_limits["max_short_reduce"],
                "total_long_available": position_limits["total_long_size"],
                "total_short_available": position_limits["total_short_size"]
            }

            logfire.info("Available budget calculated",
                         base_available=base_available,
                         available=available)

            return available

        except Exception as e:
            logfire.exception("Failed to calculate available budget", error=str(e))
            raise