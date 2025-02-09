from typing import Dict, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import logfire

from .anthropic import create_anthropic_client
from .gemini import GeminiClient
from .openai import OpenAIClient
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator
from ...tools.redis.order_context import OrderContext
from ...models import TradingParameters, TradingPlan

class TradingPlanner:
    def __init__(self, market_data: MarketDataTool, orders: OrdersTool,
                chart_generator: ChartGeneratorTool, provider_name: str,
                api_key: str, vertex_params: Optional[Dict] = None):
        self.market_data = market_data
        self.orders = orders
        self.chart_generator = chart_generator
        self.volatility_calculator = VolatilityCalculator()

        if provider_name.startswith("anthropic"):
            self.ai_client = create_anthropic_client(provider_name, api_key, **(vertex_params or {}))
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
        logfire.info("Trading planner initialized", ai_provider=provider_name)

    def create_plan(self, params: TradingParameters) -> TradingPlan:
        from .generator import PlanGenerator
        generator = PlanGenerator(
            market_data=self.market_data,
            orders=self.orders,
            chart_generator=self.chart_generator,
            volatility_calculator=self.volatility_calculator,
            order_context=self.order_context,  # Usa l'order_context dal container
            ai_client=self.ai_client,
            system_template=self.system_template
        )
        return generator.generate(params)

    def execute_plan(self, plan: TradingPlan) -> Dict:
        from .execution import PlanExecutor
        executor = PlanExecutor(
            market_data=self.market_data,
            orders=self.orders
        )
        return executor.execute(plan)