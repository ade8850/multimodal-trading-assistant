from typing import Dict, Any
from jinja2 import Template
import logfire

from ...models import (
    TradingParameters, TradingPlan, ExistingOrder
)
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator, TimeframeVolatility
from .analysis import MarketAnalyzer
from .base import BaseAIClient


def _convert_pydantic_to_dict(obj: Any) -> Any:
    """Convert Pydantic objects to plain dictionaries recursively."""
    if hasattr(obj, 'model_dump'):
        # Per i modelli Pydantic più recenti che usano model_dump
        obj_dict = obj.model_dump()
    elif hasattr(obj, 'dict'):
        # Per compatibilità con versioni precedenti
        obj_dict = obj.dict()
    else:
        return obj

    # Converte ricorsivamente i valori del dizionario
    for key, value in obj_dict.items():
        if hasattr(value, 'model_dump') or hasattr(value, 'dict'):
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
                 ai_client: BaseAIClient,
                 system_template: Template):
        """Initialize the plan generator.
        
        Args:
            market_data: Service for market data operations
            orders: Service for order management
            chart_generator: Service for chart generation
            volatility_calculator: Service for volatility metrics
            ai_client: AI provider client
            system_template: Jinja template for system prompt
        """
        self.market_analyzer = MarketAnalyzer(
            market_data=market_data,
            chart_generator=chart_generator,
            volatility_calculator=volatility_calculator
        )
        self.orders = orders
        self.ai_client = ai_client
        self.system_template = system_template

    def generate(self, params: TradingParameters) -> TradingPlan:
        """Generate a complete trading plan.
        
        Args:
            params: Trading parameters for plan generation
            
        Returns:
            Complete trading plan with analysis and orders
        """
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

                # Generate template variables
                template_vars = self._prepare_template_vars(
                    params=params,
                    market_data=market_data,
                    positions_orders=positions_orders
                )

                # Generate system prompt
                system_prompt = self.system_template.render(**template_vars)

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
        """Fetch current positions and orders."""
        positions = []
        existing_orders = []

        try:
            with logfire.span("fetch_positions_orders"):
                # Get current positions
                positions = self.orders.get_positions(symbol)
                logfire.info("Current positions fetched", count=len(positions))

                # Get active orders
                active_orders = self.orders.get_active_orders(symbol)
                existing_orders = [ExistingOrder(**order) for order in active_orders]
                logfire.info("Active orders fetched", count=len(existing_orders))

        except Exception as e:
            logfire.error("Failed to fetch positions/orders", error=str(e))

        return {
            "current_positions": positions,
            "existing_orders": existing_orders
        }

    def _prepare_template_vars(self, 
                             params: TradingParameters,
                             market_data: Dict,
                             positions_orders: Dict) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        from ...models import generate_uuid_short

        # Generate unique IDs for this plan
        plan_id = generate_uuid_short(8)
        session_id = generate_uuid_short(4)

        # Get volatility metrics and convert to plain dict if present
        volatility_metrics = market_data.get("volatility_metrics")
        if isinstance(volatility_metrics, TimeframeVolatility):
            vol_metrics_dict = _convert_pydantic_to_dict(volatility_metrics)
            
            # Log detailed metrics for debugging
            for timeframe, metrics in vol_metrics_dict.get("metrics", {}).items():
                logfire.info(f"Volatility metrics for {timeframe}",
                           timeframe=timeframe,
                           direction_score=metrics.get("direction_score"),
                           opportunity_score=metrics.get("opportunity_score"),
                           regime=metrics.get("regime"),
                           atr=metrics.get("atr"),
                           atr_percentile=metrics.get("atr_percentile"))
        else:
            vol_metrics_dict = None
            logfire.warning("No volatility metrics available")

        # Convert existing orders to plain dicts
        existing_orders = [_convert_pydantic_to_dict(order) 
                         for order in positions_orders["existing_orders"]]

        template_vars = {
            "plan_id": plan_id,
            "session_id": session_id,
            "current_price": market_data["current_price"],
            "symbol": params.symbol,
            "budget": params.budget,
            "leverage": params.leverage,
            "existing_orders": existing_orders,
            "current_positions": positions_orders["current_positions"],
            "volatility_metrics": vol_metrics_dict,
            "atr_timeframe": params.stop_loss_config.get("timeframe") if params.stop_loss_config else "1H"
        }

        logfire.info("Template variables prepared", **{
            k: v for k, v in template_vars.items() 
            if not isinstance(v, (list, dict))  # Log solo valori scalari
        })
        logfire.debug("Full template variables", template_vars=template_vars)

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