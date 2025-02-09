# aitrading/container.py

from dependency_injector import containers, providers
from .tools.bybit.market_data import MarketDataTool
from .tools.bybit.orders import OrdersTool
from .tools.charts import ChartGeneratorTool
from .tools.redis.provider import RedisProvider
from .tools.redis.order_context import OrderContext
from .tools.stop_loss import StopLossManager
from .agents.planner.planner import TradingPlanner


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    config = providers.Configuration()

    # Redis provider (optional)
    redis_provider = providers.Singleton(
        RedisProvider,
        enabled=providers.Callable(
            lambda config: config.get("redis", {}).get("enabled", False),
            config
        ),
        host=providers.Callable(
            lambda config: config.get("redis", {}).get("host", "localhost"),
            config
        ),
        port=providers.Callable(
            lambda config: config.get("redis", {}).get("port", 6379),
            config
        ),
        db=providers.Callable(
            lambda config: config.get("redis", {}).get("db", 0),
            config
        ),
        password=providers.Callable(
            lambda config: config.get("redis", {}).get("password", ""),
            config
        ),
        ssl=providers.Callable(
            lambda config: config.get("redis", {}).get("ssl", False),
            config
        ),
        key_prefix=providers.Callable(
            lambda config: config.get("redis", {}).get("key_prefix", "trading:"),
            config
        )
    )

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

    # Stop Loss Manager
    stop_loss_manager = providers.Singleton(
        StopLossManager,
        market_data=market_data,
        orders=orders,
        config=providers.Callable(
            lambda config: {
                "timeframe": config.get("stop_loss", {}).get("timeframe", "1H"),
                "initial_multiplier": config.get("stop_loss", {}).get("initial_multiplier", 1.5),
                "in_profit_multiplier": config.get("stop_loss", {}).get("in_profit_multiplier", 2.0)
            },
            config
        ),
        enabled=providers.Callable(
            lambda config: config.get("stop_loss", {}).get("enabled", True),
            config
        )
    )

    # Order context manager
    order_context = providers.Singleton(
        OrderContext,
        redis_provider=redis_provider
        # TTL has a default value of 30 days in OrderContext class
    )

    # Trading Planner with AI configuration
    trading_planner = providers.Singleton(
        TradingPlanner,
        market_data=market_data,
        orders=orders,
        chart_generator=chart_generator,
        order_context=order_context,
        provider_name=providers.Callable(
            lambda config: config["llm"]["provider"],
            config
        ),
        api_key=providers.Callable(
            lambda config: config["llm"]["api_key"],
            config
        ),
        vertex_params=providers.Callable(
            lambda config: {
                "vertex_project": config["llm"].get("vertex_project"),
                "vertex_region": config["llm"].get("vertex_region")
            } if config["llm"]["provider"] == "anthropic-vertex" else None,
            config
        ),
        stop_loss_manager=stop_loss_manager,
    )