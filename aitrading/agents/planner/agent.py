from typing import Dict, List
from datetime import datetime, timedelta
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader
import os
import time
from contextlib import nullcontext

import logfire

from .anthropic import AnthropicClient
from .gemini import GeminiClient
from .openai import OpenAIClient
from ...models import (
    TradingParameters, TradingPlan, ExistingOrder,
    OrderCancellation, generate_uuid_short,
)
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator
from ...tools.stop_loss import StopLossManager, StopLossConfig

class TradingPlanner:
    def __init__(self, market_data: MarketDataTool, orders: OrdersTool, 
                chart_generator: ChartGeneratorTool, provider_name: str, api_key: str):
        self.market_data = market_data
        self.orders = orders
        self.chart_generator = chart_generator
        self.volatility_calculator = VolatilityCalculator()

        if provider_name == "anthropic":
            self.ai_client = AnthropicClient(api_key)
        elif provider_name == "openai":
            self.ai_client = OpenAIClient(api_key)
        elif provider_name == "gemini":
            self.ai_client = GeminiClient(api_key)
        else:
            raise ValueError(f"Unsupported AI provider: {provider_name}")

        template_dir = Path(__file__).parent / "prompts"
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.system_template = self.env.get_template("system_prompt.j2")

        try:
            logfire.info("Trading planner initialized", ai_provider=provider_name)
        except Exception as e:
            logfire.exception(f"Failed to initialize Logfire: {str(e)}")

    def create_trading_plan(self, params: TradingParameters) -> TradingPlan:
        """Create a new trading plan with analysis and planned orders."""
        try:
            with logfire.span("create_trading_plan") as span:
                span.set_attributes({
                    "symbol": params.symbol,
                    "budget": params.budget,
                    "leverage": params.leverage,
                })

                plan_id = generate_uuid_short(8)
                session_id = generate_uuid_short(4)

                # Get market data and volatility metrics
                with logfire.span("fetch_market_data"):
                    current_price = self.market_data.get_current_price(params.symbol)
                    timeframes = self.market_data.get_analysis_timeframes()

                    timeframe_data = {}
                    for timeframe in timeframes:
                        df = self.market_data.fetch_historical_data(params.symbol, timeframe)
                        timeframe_data[timeframe] = df

                # Calculate volatility metrics
                try:
                    with logfire.span("calculate_volatility"):
                        volatility_metrics = self.volatility_calculator.calculate_for_timeframes(timeframe_data)
                except Exception as e:
                    volatility_metrics = None
                    logfire.error("Volatility calculation failed", error=str(e))

                # Get active orders
                try:
                    with logfire.span("fetch_active_orders"):
                        active_orders = self.orders.get_active_orders(params.symbol)
                        existing_orders = [ExistingOrder(**order) for order in active_orders]
                        logfire.info("Active orders fetched", count=len(existing_orders))
                except Exception as e:
                    existing_orders = []
                    logfire.error("Failed to fetch active orders", error=str(e))

                # Get current positions
                try:
                    with logfire.span("fetch_positions"):
                        current_positions = self.orders.get_positions(params.symbol)
                        logfire.info("Current positions fetched", count=len(current_positions))
                except Exception as e:
                    current_positions = []
                    logfire.error("Failed to fetch positions", error=str(e))

                # Generate analysis charts
                with logfire.span("generate_charts"):
                    charts = self._generate_analysis_charts(params.symbol, timeframes)
                    if not charts:
                        raise ValueError("Failed to generate analysis charts")

                # Prepare template variables and generate system prompt
                template_vars = {
                    "plan_id": plan_id,
                    "session_id": session_id,
                    "current_price": current_price,
                    "symbol": params.symbol,
                    "budget": params.budget,
                    "leverage": params.leverage,
                    "existing_orders": existing_orders,
                    "current_positions": current_positions,
                    "volatility_metrics": volatility_metrics
                }

                system_prompt = self.system_template.render(**template_vars)

                # Get AI response
                with logfire.span("generate_strategy") as strategy_span:
                    strategy_span.set_attributes({
                        "ai_provider": self.ai_client.__class__.__name__,
                        "charts_count": len(charts)
                    })
                    response_dict = self.ai_client.generate_strategy(system_prompt, charts)

                # Create plan from response
                if 'plan' not in response_dict:
                    raise ValueError("AI response missing plan data")

                # Initialize trading plan
                plan_data = response_dict['plan']
                plan_data['id'] = plan_id
                plan_data['session_id'] = session_id
                plan_data['parameters'] = params
                trading_plan = TradingPlan(**plan_data)

                logfire.info("Trading plan created", **trading_plan.dict())

                return trading_plan

        except Exception as e:
            logfire.error("Error creating trading plan", error=str(e))
            raise Exception(f"Error creating trading plan: {str(e)}")

    def _generate_analysis_charts(self, symbol: str, timeframes: List[str]) -> List[bytes]:
        """Generate technical analysis charts for each timeframe."""
        generated_charts = []
        dump_charts = os.getenv('DUMP_CHARTS', '').lower() in ('true', '1', 'yes')

        try:
            # Create .graphs directory if it doesn't exist
            graphs_dir = Path('.graphs')
            graphs_dir.mkdir(exist_ok=True)

            # Clean only files related to the current symbol
            if graphs_dir.exists():
                symbol_pattern = f"{symbol}_*"
                for file in graphs_dir.glob(symbol_pattern):
                    try:
                        if file.is_file():
                            file.unlink()
                    except Exception as e:
                        logfire.warning(f"Could not remove file {file}: {str(e)}")

            logfire.debug(f"Cleaned charts for symbol {symbol} in .graphs directory")

            for timeframe in timeframes:
                try:
                    with logfire.span(f"generate_chart_{timeframe}"):
                        # Fetch historical data
                        df = self.market_data.fetch_historical_data(symbol, timeframe)

                        # Generate multiple charts for this timeframe
                        timeframe_charts = self.chart_generator.create_charts_for_timeframe(df, timeframe)
                        if timeframe_charts:
                            generated_charts.extend(timeframe_charts)

                            # Save charts if DUMP_CHARTS is enabled
                            if dump_charts:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                for i, chart in enumerate(timeframe_charts):
                                    filename = f"{symbol}_{timeframe}_view{i}_{timestamp}.png"
                                    filepath = graphs_dir / filename
                                    try:
                                        with open(filepath, 'wb') as f:
                                            f.write(chart)
                                        logfire.debug(f"Saved chart: {filename}")
                                    except Exception as e:
                                        logfire.warning(f"Could not save chart {filename}: {str(e)}")

                except Exception as e:
                    logfire.exception(f"Error generating charts for {timeframe}: {str(e)}")

            logfire.info("Charts generated", **{
                "charts_count": len(generated_charts),
                "symbol": symbol,
                "timeframes": timeframes
            })

            return generated_charts

        except Exception as e:
            logfire.exception(f"Error in chart generation: {str(e)}")
            return generated_charts  # Return any charts we managed to generate

    def execute_plan(self, plan: TradingPlan) -> Dict:
        """Execute all operations in the trading plan on the exchange."""
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
                    "orders": []
                }

                # Execute cancellations first
                if plan.cancellations:
                    with logfire.span("execute_cancellations"):
                        cancellation_results = self._execute_cancellations(plan.cancellations)
                        results["cancellations"] = cancellation_results
                    time.sleep(1)

                # Initialize StopLossManager if configuration is provided
                stop_loss_manager = None
                if plan.parameters.stop_loss_config:
                    stop_loss_config = StopLossConfig(**plan.parameters.stop_loss_config)
                    stop_loss_manager = StopLossManager(
                        market_data=self.market_data,
                        orders=self.orders,
                        config=stop_loss_config
                    )

                # Execute new orders
                if plan.orders:
                    with logfire.span("execute_orders"):
                        for order in plan.orders:
                            try:
                                self.orders.set_position_settings(
                                    symbol=order.symbol,
                                    leverage=order.order.entry.leverage
                                )

                                result = self.orders.place_strategy_orders(order)
                                if result.get("errors"):
                                    raise ValueError(f"Order execution failed for {order.id}: {result['errors']}")

                                results["orders"].append({
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
                                results["orders"].append({
                                    "order_id": order.id,
                                    "order_link_id": order.order_link_id,
                                    "error": str(e)
                                })
                                logfire.error("Order placement failed", **{
                                    "order_id": order.id,
                                    "symbol": order.symbol,
                                    "error": str(e)
                                })

                # Update stop losses if manager is initialized
                if stop_loss_manager:
                    with logfire.span("update_stop_losses"):
                        try:
                            stop_loss_results = stop_loss_manager.update_position_stops(plan.parameters.symbol)
                            results["stop_loss_updates"] = stop_loss_results
                        except Exception as e:
                            logfire.error("Stop loss update failed", error=str(e))

                logfire.info("Plan execution complete", **{
                    "plan_id": plan.id,
                    "successful_cancellations": sum(1 for c in results["cancellations"] if c.get("status") == "success"),
                    "successful_orders": sum(1 for o in results["orders"] if "error" not in o)
                })

                return results

        except Exception as e:
            logfire.exception("Plan execution failed", **{"error": str(e), "plan_id": plan.id})
            raise Exception(f"Error executing trading plan: {str(e)}")

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