from typing import Dict
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import logfire

from .anthropic import AnthropicClient
from .gemini import GeminiClient
from .openai import OpenAIClient
from ...tools.bybit.market_data import MarketDataTool
from ...tools.bybit.orders import OrdersTool
from ...tools.charts import ChartGeneratorTool
from ...tools.volatility import VolatilityCalculator
from ...models import TradingParameters, TradingPlan

class TradingPlanner:
    """Main trading planner class that coordinates analysis and execution."""
    
    def __init__(self, market_data: MarketDataTool, orders: OrdersTool, 
                chart_generator: ChartGeneratorTool, provider_name: str, api_key: str):
        """Initialize the trading planner with required services.
        
        Args:
            market_data: Service for market data operations
            orders: Service for order management
            chart_generator: Service for chart generation
            provider_name: AI provider name (anthropic/gemini/openai)
            api_key: AI provider API key
        """
        # Initialize core services
        self.market_data = market_data
        self.orders = orders
        self.chart_generator = chart_generator
        self.volatility_calculator = VolatilityCalculator()

        # Initialize AI client based on provider
        if provider_name == "anthropic":
            self.ai_client = AnthropicClient(api_key)
        elif provider_name == "openai":
            self.ai_client = OpenAIClient(api_key)
        elif provider_name == "gemini":
            self.ai_client = GeminiClient(api_key)
        else:
            raise ValueError(f"Unsupported AI provider: {provider_name}")

        # Setup template engine
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

    def create_plan(self, params: TradingParameters) -> TradingPlan:
        """Create a new trading plan.
        
        This is the main entry point for plan creation. It delegates to the
        PlanGenerator class for the actual plan generation.
        
        Args:
            params: Trading parameters for plan generation
            
        Returns:
            Complete trading plan with analysis and orders
        """
        from .generator import PlanGenerator
        generator = PlanGenerator(
            market_data=self.market_data,
            orders=self.orders,
            chart_generator=self.chart_generator,
            volatility_calculator=self.volatility_calculator,
            ai_client=self.ai_client,
            system_template=self.system_template
        )
        return generator.generate(params)

    def execute_plan(self, plan: TradingPlan) -> Dict:
        """Execute a trading plan.
        
        This is the main entry point for plan execution. It delegates to the
        PlanExecutor class for the actual execution.
        
        Args:
            plan: Trading plan to execute
            
        Returns:
            Execution results including order and cancellation statuses
        """
        from .execution import PlanExecutor
        executor = PlanExecutor(
            market_data=self.market_data,
            orders=self.orders
        )
        return executor.execute(plan)