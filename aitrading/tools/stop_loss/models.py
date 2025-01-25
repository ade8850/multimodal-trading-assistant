from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ProfitBand(str, Enum):
    """Profit bands for dynamic stop loss management."""
    INITIAL = "initial"          # breakeven or small loss
    FIRST_PROFIT = "first"      # > 1% profit
    SECOND_PROFIT = "second"    # > 2% profit

class StopLossConfig(BaseModel):
    """Configuration for stop loss calculation."""
    timeframe: str = Field("1H", description="Timeframe for ATR calculation")
    initial_multiplier: float = Field(1.5, description="ATR multiplier for initial band")
    first_profit_multiplier: float = Field(2.0, description="ATR multiplier for first profit band")
    second_profit_multiplier: float = Field(2.5, description="ATR multiplier for second profit band")
    first_profit_threshold: float = Field(1.0, description="Threshold % for first profit band")
    second_profit_threshold: float = Field(2.0, description="Threshold % for second profit band")

class StopLossUpdate(BaseModel):
    """Stop loss update calculation result."""
    symbol: str
    current_price: float
    entry_price: float
    position_size: float
    current_band: ProfitBand
    current_profit_percentage: float
    atr_value: float
    new_stop_loss: float
    previous_stop_loss: Optional[float] = None
    multiplier_used: float
    reason: str