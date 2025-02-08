# aitrading/container.py

from dependency_injector import containers, providers
from .tools.bybit.market_data import MarketDataTool
from .tools.bybit.orders import OrdersTool
from .tools.charts import ChartGeneratorTool
from .tools.redis.provider import RedisProvider
from .agents.planner.planner import TradingPlanner


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    config = providers.Configuration()

    # Redis provider
    redis_provider = providers.Singleton(
        RedisProvider,
        enabled=config.redis.enabled.as_bool(default=False),
        host=config.redis.host.as_str(default="localhost"),
        port=config.redis.port.as_int(default=6379),
        db=config.redis.db.as_int(default=0),
        password=config.redis.password.as_str(default=None),
        ssl=config.redis.ssl.as_bool(default=False),
        key_prefix=config.redis.key_prefix.as_str(default="trading:"),
        ttl=config.redis.ttl.as_int(default=3600)
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
        ),
        vertex_params=providers.Callable(
            lambda config: {
                "vertex_project": config["llm"].get("vertex_project"),
                "vertex_region": config["llm"].get("vertex_region")
            } if config["llm"]["provider"] == "anthropic-vertex" else None,
            config
        )
    )