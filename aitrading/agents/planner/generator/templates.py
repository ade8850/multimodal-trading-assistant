from typing import Dict, Any, List
from datetime import datetime, timezone
import os
import json
import logfire

from ....models.base import generate_uuid_short
from ....models.trading import TradingParameters
from ....tools.volatility.models import TimeframeVolatility
from .budget import BudgetCalculator
from .orders import OrderProcessor


class TemplateManager:
    """Handles template preparation and variable management."""

    def __init__(self, budget_calculator: BudgetCalculator, order_processor: OrderProcessor):
        """Initialize with required processors."""
        self.budget_calculator = budget_calculator
        self.order_processor = order_processor

    def prepare_template_vars(self,
                            params: TradingParameters,
                            market_data: Dict,
                            positions_orders: Dict,
                            positions_budget: float,
                            orders_budget: float) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        from .utils import convert_pydantic_to_dict
        
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
                existing_orders = self.order_processor.process_existing_orders(
                    positions_orders["existing_orders"]
                )

                # Calculate position-based limits
                position_limits = self.budget_calculator.calculate_position_limits(
                    positions_orders["current_positions"]
                )

                # Calculate available budget considering reduce-only orders
                available_budget = self.budget_calculator.calculate_available_budget(
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
                    "current_datetime": datetime.now(timezone.utc).isoformat(),
                    # Add execution context parameters
                    "parameters": {
                        "execution_mode": params.execution_mode,
                        "analysis_interval": params.analysis_interval
                    }
                }

                logfire.info("Template variables prepared",
                            template_vars=convert_pydantic_to_dict(template_vars))

                return template_vars

        except Exception as e:
            logfire.exception("Failed to prepare template variables", error=str(e))
            raise

    def save_rendered_prompt(self, system_prompt: str) -> None:
        """Save rendered prompt to file if enabled."""
        try:
            prompt_file = os.environ.get('RENDERED_PROMPT_FILE')
            if not prompt_file:
                return

            try:
                with open(prompt_file, 'w') as f:
                    f.write(system_prompt)
                logfire.info(f"Saved rendered prompt to {prompt_file}")
            except Exception as e:
                logfire.error(f"Error saving rendered prompt: {str(e)}")

        except Exception as e:
            logfire.error("Error in save_rendered_prompt", error=str(e))

    def generate_ai_response(self, 
                           system_prompt: str, 
                           charts: list,
                           ai_client: Any) -> Dict[str, Any]:
        """Get response from AI provider."""
        with logfire.span("generate_strategy") as span:
            span.set_attributes({
                "ai_provider": ai_client.__class__.__name__,
                "charts_count": len(charts)
            })

            response_dict = ai_client.generate_strategy(system_prompt, charts)

            if 'plan' not in response_dict:
                raise ValueError("AI response missing plan data")
            return response_dict['plan']