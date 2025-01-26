import os
import sys
import yaml
import signal
import asyncio
import warnings
from typing import Dict, Any
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install
from dependency_injector.wiring import inject, Provide

import logfire

from aitrading.models import TradingParameters
from aitrading.container import Container


# Install rich traceback handler
install(show_locals=True)

# Suppress the escape sequence warning from pybit
warnings.filterwarnings("ignore", category=SyntaxWarning)

logfire.configure(
    environment=os.environ.get("LOGFIRE_ENVIRONMENT", "scheduler"),
    send_to_logfire="if-token-present",
    scrubbing=False,
)

class TradingScheduler:
    """Scheduler for automated trading strategy execution."""

    def __init__(self, config_path: str):
        """Initialize the scheduler with configuration."""
        self.config_path = config_path
        self.running = False
        self.config = self._load_config()
        self.container = self._init_container()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logfire.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logfire.error(f"Error loading configuration: {str(e)}")
            raise

    def _init_container(self) -> Container:
        """Initialize the dependency injection container."""
        container = Container()

        # Configure container with default provider
        container.config.update({
            "bybit": {
                "api_key": os.getenv("BYBIT_API_KEY"),
                "api_secret": os.getenv("BYBIT_API_SECRET"),
                "testnet": os.getenv("BYBIT_TESTNET", "False").lower() == "true"
            },
            "llm": {
                "provider": self.config.get("ai_provider", "anthropic"),
                "api_key": (
                    os.getenv("ANTHROPIC_API_KEY") if self.config.get("ai_provider") == "anthropic"
                    else os.getenv("GEMINI_API_KEY") if self.config.get("ai_provider") == "gemini"
                    else os.getenv("OPENAI_API_KEY")
                )
            }
        })

        logfire.debug("Container initialized")

        container.wire(modules=["__main__"])
        return container

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle termination signals."""
        logfire.info("Received termination signal - initiating shutdown")
        self.running = False

    async def _execute_strategy(self, symbol: str, params: Dict[str, Any]) -> None:
        """Execute trading strategy for a single symbol."""
        try:
            # Create trading parameters
            trading_params = TradingParameters(
                symbol=symbol,
                budget=float(params["budget"]),
                leverage=int(params["leverage"]),
                stop_loss_config=self.config.get("stop_loss")
            )

            # Generate and execute trading plan
            planner = self.container.trading_planner()
            trading_plan = planner.create_trading_plan(trading_params)

            if trading_plan:
                with logfire.span("executing_plan") as span:
                    span.set_attribute("symbol", symbol)
                    # Execute the plan
                    result = await planner.execute_plan(trading_plan)

                    logfire.info("Executing results", extra=result)
                    if result.get("cancellations"):
                        for cancel in result["cancellations"]:
                            if cancel.get("status") == "success":
                                logfire.info("Success cancel", extra={"order_link_id": cancel['order_link_id']})
                            else:
                                logfire.error("Failed cancel", extra={
                                    "order_link_id": cancel['order_link_id'],
                                    "error": cancel.get('error')
                                })
                    if result.get("position_updates"):
                        for update in result["position_updates"]:
                            if update.get("success"):
                                logfire.info("Success update")
                            else:
                                logfire.error("Failed update", extra={"error": update.get("error")})

                    if result.get("orders"):
                        for order in result["orders"]:
                            if "error" not in order:
                                logfire.info("New order created")
                            else:
                                logfire.error("Failed order creation", extra={"error": order["error"]})

                    # Log stop loss updates
                    if result.get("stop_loss_updates"):
                        logfire.info("Stop loss updates", extra=result["stop_loss_updates"])
            else:
                logfire.warning(f"No trading plan generated")

        except Exception as e:
            logfire.exception(f"Error executing strategy: {str(e)}")

    async def run(self) -> None:
        """Main scheduling loop."""
        self.running = True
        interval = self.config.get("interval_minutes", 60)

        logfire.info(f"Starting trading scheduler", extra={"interval": interval})

        while self.running:
            start_time = datetime.now()

            try:
                # Process each symbol sequentially
                for symbol, params in self.config.get("symbols", {}).items():
                    if not self.running:
                        break

                    logfire.info(f"Processing {symbol}")
                    await self._execute_strategy(symbol, params)

                    # Short pause between symbols
                    await asyncio.sleep(1)

                # Calculate time until next run
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, (interval * 60) - elapsed)

                if sleep_time > 0 and self.running:
                    next_run = datetime.now().timestamp() + sleep_time
                    logfire.info(f"Next run at {datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')}")
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                logfire.exception(f"Error in main loop: {str(e)}")

                # Wait before retrying
                if self.running:
                    await asyncio.sleep(60)

        logfire.info("Scheduler stopped")


def main():
    """Entrypoint for the scheduler."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get configuration path
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if not Path(config_path).exists():
        logfire.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    # Create and run scheduler
    scheduler = TradingScheduler(config_path)

    try:
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        logfire.info("Scheduler terminated by user")
    except Exception as e:
        logfire.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()