# aitrading/tools/bybit/market_data.py

from typing import Dict, List
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from ..charts.config import TimeframesConfiguration

import logging
logger = logging.getLogger("trader")


class MarketDataTool:
    """Tool for fetching market data from Bybit."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.session = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
        self.config = TimeframesConfiguration()

    def get_analysis_timeframes(self) -> List[str]:
        """Get all available analysis timeframes."""
        logger.info("Getting available timeframes")
        try:
            timeframes = self.config.get_base_timeframes()
            logger.info(f"Retrieved timeframes: {timeframes}")
            return timeframes
        except Exception as e:
            logger.error(f"Error getting timeframes: {str(e)}")
            raise

    def get_current_price(self, symbol: str) -> float:
        """Get current market price."""
        try:
            response = self.session.get_tickers(category="linear", symbol=symbol)
            return float(response["result"]["list"][0]["lastPrice"])
        except Exception as e:
            raise Exception(f"Error fetching price: {str(e)}")

    def fetch_historical_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Fetch historical market data for specified timeframe."""
        logger.info(f"Fetching data for {symbol} on {timeframe} timeframe")
        try:
            # Get timeframe configuration
            tf_config = self.config.get_timeframe_config(timeframe)
            logger.info(f"Using interval: {tf_config.interval} for timeframe: {timeframe}")

            # Get data from Bybit
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=tf_config.interval,
                start=self._get_start_timestamp(tf_config),
                limit=tf_config.candles,
            )

            if response["retCode"] != 0:
                raise ValueError(f"API error: {response['retMsg']}")

            data = self._process_kline_data(response["result"]["list"])
            logger.info(f"Retrieved {len(data)} candles for {timeframe}")
            return data

        except Exception as e:
            logger.error(f"Error fetching historical data for {timeframe}: {str(e)}")
            raise Exception(f"Error fetching historical data: {str(e)}")

    def _get_start_timestamp(self, tf_config: Dict) -> int:
        """Calculate start timestamp based on timeframe configuration."""
        now = datetime.now()
        lookback_minutes = tf_config.candles * tf_config.minutes
        start_time = now - timedelta(minutes=lookback_minutes)
        return int(start_time.timestamp() * 1000)

    def _process_kline_data(self, data: List) -> pd.DataFrame:
        """Process raw kline data into DataFrame."""
        if not data:
            raise ValueError("No data returned")

        df = pd.DataFrame(
            data,
            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],
        )

        # Convert numeric columns
        numeric_cols = ["open", "high", "low", "close", "volume", "turnover"]
        df[numeric_cols] = df[numeric_cols].astype(float)

        # Process timestamp
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
        df.set_index("timestamp", inplace=True)

        return df.sort_index()