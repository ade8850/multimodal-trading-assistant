from typing import Dict, List, Any
from jinja2 import Template
import logfire

from ....models.trading import TradingParameters, TradingPlan
from ....tools.bybit.market_data import MarketDataTool
from ....tools.bybit.orders import OrdersTool
from ....tools.charts import ChartGeneratorTool
from ....tools.redis.order_context import OrderContext
from ....tools.volatility import VolatilityCalculator
from ....models.position import Position
from ....models.orders import PlannedOrder, ExistingOrder

from .budget import BudgetCalculator
from .orders import OrderProcessor
from .templates import TemplateManager
from ..analysis import MarketAnalyzer


class PlanGenerator:
    """Main class for generating trading plans."""

    def __init__(self,
                 market_data: MarketDataTool,
                 orders: OrdersTool,
                 chart_generator: ChartGeneratorTool,
                 volatility_calculator: VolatilityCalculator,
                 order_context: OrderContext,
                 ai_client: Any,
                 system_template: Template,
                 ai_stream_manager=None):
        """Initialize the plan generator with required components."""
        self.market_analyzer = MarketAnalyzer(
            market_data=market_data,
            chart_generator=chart_generator,
            volatility_calculator=volatility_calculator
        )
        self.orders = orders
        self.ai_client = ai_client
        self.system_template = system_template
        self.ai_stream_manager = ai_stream_manager
        
        # Initialize processors
        self.budget_calculator = BudgetCalculator()
        self.order_processor = OrderProcessor(order_context)
        self.template_manager = TemplateManager(
            budget_calculator=self.budget_calculator,
            order_processor=self.order_processor,
            ai_stream_manager=ai_stream_manager
        )

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
                positions_budget, orders_budget = self.budget_calculator.calculate_allocated_budget(
                    positions_orders["current_positions"],
                    positions_orders["existing_orders"],
                    market_data["current_price"]
                )

                # Generate template variables
                template_vars = self.template_manager.prepare_template_vars(
                    params=params,
                    market_data=market_data,
                    positions_orders=positions_orders,
                    positions_budget=positions_budget,
                    orders_budget=orders_budget
                )

                # Generate system prompt
                system_prompt = self.system_template.render(**template_vars)

                # Save rendered prompt if configured
                self.template_manager.save_rendered_prompt(system_prompt)

                # Get AI response
                plan_data = self.template_manager.generate_ai_response(
                    system_prompt=system_prompt,
                    charts=market_data["charts"],
                    ai_client=self.ai_client
                )

                # Create and validate trading plan
                trading_plan = self._create_trading_plan(
                    plan_data=plan_data,
                    params=params,
                    current_positions=positions_orders["current_positions"]
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
                    order: ExistingOrder
                    try:
                        context_data = self.order_processor.order_context.get_context(order.order_link_id)
                        if context_data and "data" in context_data:
                            # Create StrategicContext from saved data
                            strategic_context = context_data["data"]
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

    def _create_trading_plan(self, plan_data: Dict, params: TradingParameters, current_positions: List[Position]) -> TradingPlan:
        """Create and validate trading plan from AI response."""
        try:
            # Process orders
            processed_orders = self.order_processor.create_trading_plan_orders(
                plan_data=plan_data,
                params=params,
                current_positions=current_positions
            )

            # Create trading plan with processed orders
            trading_plan_kwargs = dict(
                id=plan_data['id'],
                session_id=plan_data['session_id'],
                parameters=params,
                orders=processed_orders,
                cancellations=plan_data.get('cancellations'),
                analysis=plan_data['analysis']
            )

            logfire.info("Trading Plan Params", **trading_plan_kwargs)

            trading_plan = TradingPlan(**trading_plan_kwargs)

            # Save strategic context for each order
            for order in trading_plan.orders:
                self.order_processor.save_strategic_context(order)

            return trading_plan

        except Exception as e:
            logfire.error("Failed to create trading plan", error=str(e))
            raise