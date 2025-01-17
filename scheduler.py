# scheduler.py

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
import logging
from dependency_injector.wiring import inject, Provide

from aitrading.models import TradingParameters
from aitrading.container import Container

# Initialize Rich console first
console = Console()

# Install rich traceback handler
install(show_locals=True)

# Suppress the escape sequence warning from pybit
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Configure logging with Rich
logger = logging.getLogger("trader")
logger.setLevel(logging.INFO)

# Configure log format
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add Rich handler for console output
console_handler = RichHandler(
    rich_tracebacks=True,
    markup=True,
    show_path=False,
    enable_link_path=False
)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

# Add file handler
try:
    file_handler = logging.FileHandler('scheduler.log')
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
except Exception as e:
    console.print(f"[yellow]Warning: Could not setup file logging: {str(e)}[/yellow]")


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
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
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

        container.wire(modules=["__main__"])
        return container

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle termination signals."""
        logger.info("Received termination signal - initiating shutdown")
        self.running = False

    async def _execute_strategy(self, symbol: str, params: Dict[str, Any]) -> None:
        """Execute trading strategy for a single symbol."""
        try:
            # Create trading parameters
            trading_params = TradingParameters(
                symbol=symbol,
                budget=float(params["budget"]),
                leverage=int(params["leverage"]),
                strategy_instructions=params.get("strategy_instructions", "")
            )

            # Generate and execute trading plan
            trading_plan = self.container.trading_planner().create_trading_plan(trading_params)

            if trading_plan:
                logger.info(f"Generated trading plan for {symbol}")

                with console.status(f"[bold green]Executing plan for {symbol}..."):
                    # Execute the plan
                    result = self.container.trading_planner().execute_plan(trading_plan)

                    # Log results using Rich tables
                    console.print(f"\n[bold green]Execution Results for {symbol}[/bold green]")

                    if result.get("cancellations"):
                        console.print("[yellow]Cancellations:[/yellow]")
                        for cancel in result["cancellations"]:
                            status = "[green]Success[/green]" if cancel.get(
                                "status") == "success" else f"[red]Failed: {cancel.get('error')}[/red]"
                            console.print(f"  • Order {cancel['order_link_id']}: {status}")

                    if result.get("position_updates"):
                        console.print("[yellow]Position Updates:[/yellow]")
                        for update in result["position_updates"]:
                            status = "[green]Success[/green]" if update.get(
                                "success") else f"[red]Failed: {update.get('error')}[/red]"
                            console.print(f"  • {update['symbol']}: {status}")

                    if result.get("orders"):
                        console.print("[yellow]New Orders:[/yellow]")
                        for order in result["orders"]:
                            status = "[green]Success[/green]" if "error" not in order else f"[red]Failed: {order['error']}[/red]"
                            console.print(f"  • Order {order['order_link_id']}: {status}")
            else:
                logger.warning(f"No trading plan generated for {symbol}")

        except Exception as e:
            logger.exception(f"Error executing strategy for {symbol}")

    async def run(self) -> None:
        """Main scheduling loop."""
        self.running = True
        interval = self.config.get("interval_minutes", 60)

        logger.info(f"Starting trading scheduler | Interval: {interval} minutes")

        while self.running:
            start_time = datetime.now()

            try:
                # Process each symbol sequentially
                for symbol, params in self.config.get("symbols", {}).items():
                    if not self.running:
                        break

                    logger.info(f"Processing {symbol}")
                    await self._execute_strategy(symbol, params)

                    # Short pause between symbols
                    await asyncio.sleep(1)

                # Calculate time until next run
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, (interval * 60) - elapsed)

                if sleep_time > 0 and self.running:
                    next_run = datetime.now().timestamp() + sleep_time
                    logger.info(f"Next run at {datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')}")
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.exception("Error in main loop")

                # Wait before retrying
                if self.running:
                    await asyncio.sleep(60)

        logger.info("Scheduler stopped")


def main():
    """Entrypoint for the scheduler."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get configuration path
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if not Path(config_path).exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    # Create and run scheduler
    scheduler = TradingScheduler(config_path)

    try:
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        logger.info("Scheduler terminated by user")
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()