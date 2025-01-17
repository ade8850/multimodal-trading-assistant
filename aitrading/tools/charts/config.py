from pathlib import Path
from typing import Dict, List, Optional
import yaml

from .models import TimeframeConfig, ChartConfig


class TimeframesConfigurationError(Exception):
    """Raised when there's an error in the timeframes configuration."""
    pass


class TimeframesConfiguration:
    """Manages timeframes configuration for chart generation."""
    
    def __init__(self):
        self._config: Optional[Dict] = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        config_path = Path(__file__).parent / "timeframes.yaml"
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            raise TimeframesConfigurationError(f"Error loading configuration: {str(e)}")
            
    def get_timeframe_config(self, timeframe: str) -> TimeframeConfig:
        """Get configuration for a specific timeframe."""
        if not self._config or "timeframes" not in self._config:
            raise TimeframesConfigurationError("Configuration not loaded or invalid")
            
        timeframe_data = self._config["timeframes"].get(timeframe)
        if not timeframe_data:
            raise TimeframesConfigurationError(f"Configuration not found for timeframe: {timeframe}")
            
        # Add timeframe to the data for model creation
        timeframe_data["timeframe"] = timeframe
        
        try:
            return TimeframeConfig(**timeframe_data)
        except Exception as e:
            raise TimeframesConfigurationError(
                f"Invalid configuration for timeframe {timeframe}: {str(e)}"
            )
    
    def get_base_timeframes(self) -> List[str]:
        """Get list of all available timeframes."""
        if not self._config or "timeframes" not in self._config:
            raise TimeframesConfigurationError("Configuration not loaded or invalid")
            
        return list(self._config["timeframes"].keys())
    
    def create_chart_config(self, symbol: str, timeframes: List[str]) -> ChartConfig:
        """Create chart configuration for given symbol and timeframes."""
        timeframe_configs = []
        
        for tf in timeframes:
            try:
                timeframe_config = self.get_timeframe_config(tf)
                timeframe_configs.append(timeframe_config)
            except Exception as e:
                raise TimeframesConfigurationError(
                    f"Error creating configuration for timeframe {tf}: {str(e)}"
                )
        
        return ChartConfig(symbol=symbol, timeframes=timeframe_configs)