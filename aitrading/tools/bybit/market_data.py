# aitrading/tools/bybit/market_data.py

from typing import Dict, List
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP


class MarketDataTool:
    """Tool for fetching market data from Bybit."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.session = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
        self.timeframe_configs = {
            "Short (1-7d)": ["1m", "15m", "1H", "4H"],
            "Medium (1-4w)": ["1H", "4H", "1D"],
            "Long (1-6m)": ["4H", "1D", "1W"],
        }

        self.timeframe_map = {
            "1W": "W",
            "1D": "D",
            "4H": "240",
            "1H": "60",
            "15m": "15",
            "1m": "1",
        }

    def get_analysis_timeframes(self, strategy_timeframe: str) -> List[str]:
        """Get relevant analysis timeframes for given strategy period."""
        return self.timeframe_configs.get(strategy_timeframe, ["4H", "1D"])

    def get_current_price(self, symbol: str) -> float:
        """Get current market price."""
        try:
            response = self.session.get_tickers(category="linear", symbol=symbol)
            return float(response["result"]["list"][0]["lastPrice"])
        except Exception as e:
            raise Exception(f"Error fetching price: {str(e)}")

    def fetch_historical_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Fetch historical market data for specified timeframe."""
        try:
            # Get data from Bybit
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=self.timeframe_map[timeframe],
                start=self._get_start_timestamp(timeframe),
                limit=1000,
            )

            if response["retCode"] != 0:
                raise ValueError(f"API error: {response['retMsg']}")

            return self._process_kline_data(response["result"]["list"])

        except Exception as e:
            raise Exception(f"Error fetching historical data: {str(e)}")

    def _get_start_timestamp(self, timeframe: str) -> int:
        """Calculate start timestamp based on timeframe."""
        now = datetime.now()

        configs = {
            "1W": {"candles": 53, "minutes": 7 * 24 * 60},  # ~1 year
            "1D": {"candles": 180, "minutes": 24 * 60},  # 6 months
            "4H": {"candles": 180, "minutes": 4 * 60},  # 30 days
            "1H": {"candles": 336, "minutes": 60},  # 14 days
            "15m": {"candles": 672, "minutes": 15},  # 7 days
            "1m": {"candles": 720, "minutes": 1},  # 12 hours
        }

        config = configs.get(timeframe)
        if not config:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        lookback_minutes = config["candles"] * config["minutes"]
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
