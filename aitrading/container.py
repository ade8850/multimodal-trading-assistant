# aitrading/container.py

from dependency_injector import containers, providers
from .tools.bybit.market_data import MarketDataTool
from .tools.bybit.orders import OrdersTool
from .tools.charts import ChartGeneratorTool
from .agents.planner.planner import TradingPlanner


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    config = providers.Configuration()

    # Tools
    market_data = providers.Singleton(
        MarketDataTool,
        api_key=config.bybit.api_key,
        api_secret=config.bybit.api_secret,
        testnet=config.bybit.testnet
    )

    orders = providers.Singleton(
        OrdersTool,
        api_key=config.bybit.api_key,
        api_secret=config.bybit.api_secret,
        testnet=config.bybit.testnet
    )

    chart_generator = providers.Singleton(ChartGeneratorTool)

    # Trading Planner with AI configuration
    trading_planner = providers.Singleton(
        TradingPlanner,
        market_data=market_data,
        orders=orders,
        chart_generator=chart_generator,
        provider_name=providers.Callable(
            lambda config: config["llm"]["provider"],
            config
        ),
        api_key=providers.Callable(
            lambda config: config["llm"]["api_key"],
            config
        )
    )