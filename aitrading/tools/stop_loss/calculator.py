from typing import Optional, Tuple
import pandas as pd
import logfire

from .models import StopLossConfig, StopLossUpdate, ProfitBand

class StopLossCalculator:
    """Calculator for dynamic stop loss levels based on ATR and profit bands."""

    def __init__(self, config: StopLossConfig):
        """Initialize the calculator with configuration."""
        self.config = config
        logfire.info("Stop loss calculator initialized", **config.model_dump())

    def calculate_profit_band(
        self, 
        entry_price: float, 
        current_price: float,
        position_type: str
    ) -> Tuple[ProfitBand, float, float]:
        """Calculate profit band based on current position performance.
        
        Args:
            entry_price: Position entry price
            current_price: Current market price
            position_type: Either 'long' or 'short'
            
        Returns:
            Tuple containing:
            - Current profit band
            - Profit percentage
            - ATR multiplier to use
        """
        # Calculate profit percentage
        if position_type.lower() == 'long':
            profit_percentage = ((current_price - entry_price) / entry_price) * 100
        else:  # short position
            profit_percentage = ((entry_price - current_price) / entry_price) * 100

        # Determine profit band and multiplier
        if profit_percentage >= self.config.second_profit_threshold:
            with logfire.span("profit_band_calculation") as span:
                span.set_attribute("band", "second_profit")
                span.set_attribute("profit_percentage", profit_percentage)
                return ProfitBand.SECOND_PROFIT, profit_percentage, self.config.second_profit_multiplier
        elif profit_percentage >= self.config.first_profit_threshold:
            with logfire.span("profit_band_calculation") as span:
                span.set_attribute("band", "first_profit")
                span.set_attribute("profit_percentage", profit_percentage)
                return ProfitBand.FIRST_PROFIT, profit_percentage, self.config.first_profit_multiplier
        else:
            with logfire.span("profit_band_calculation") as span:
                span.set_attribute("band", "initial")
                span.set_attribute("profit_percentage", profit_percentage)
                return ProfitBand.INITIAL, profit_percentage, self.config.initial_multiplier

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate current ATR value.
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period (default 14)
            
        Returns:
            Current ATR value
        """
        try:
            with logfire.span("atr_calculation"):
                high = df["high"]
                low = df["low"]
                close = df["close"].shift()

                tr1 = high - low
                tr2 = (high - close).abs()
                tr3 = (low - close).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(window=period).mean().iloc[-1]
                
                logfire.info("ATR calculated", value=atr, period=period)
                return float(atr)
        except Exception as e:
            logfire.error("ATR calculation failed", error=str(e))
            raise

    def calculate_stop_loss(
        self,
        symbol: str,
        current_price: float,
        entry_price: float,
        position_size: float,
        position_type: str,
        atr_value: float,
        previous_stop_loss: Optional[float] = None
    ) -> StopLossUpdate:
        """Calculate new stop loss level based on current market conditions.
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            entry_price: Position entry price
            position_size: Position size
            position_type: Either 'long' or 'short'
            atr_value: Current ATR value
            previous_stop_loss: Current active stop loss level
            
        Returns:
            StopLossUpdate object with new stop loss details
        """
        try:
            with logfire.span("stop_loss_calculation") as span:
                # Get profit band and multiplier
                band, profit_percentage, multiplier = self.calculate_profit_band(
                    entry_price, current_price, position_type
                )
                
                # Calculate new stop loss level
                atr_distance = atr_value * multiplier
                if position_type.lower() == 'long':
                    new_stop_loss = current_price - atr_distance
                    
                    # Ensure new stop loss is higher than previous (for long positions)
                    if previous_stop_loss and new_stop_loss <= previous_stop_loss:
                        span.set_attribute("stop_loss_unchanged", True)
                        return StopLossUpdate(
                            symbol=symbol,
                            current_price=current_price,
                            entry_price=entry_price,
                            position_size=position_size,
                            current_band=band,
                            current_profit_percentage=profit_percentage,
                            atr_value=atr_value,
                            new_stop_loss=previous_stop_loss,
                            previous_stop_loss=previous_stop_loss,
                            multiplier_used=multiplier,
                            reason="New stop loss would be lower than current"
                        )
                else:  # short position
                    new_stop_loss = current_price + atr_distance
                    
                    # Ensure new stop loss is lower than previous (for short positions)
                    if previous_stop_loss and new_stop_loss >= previous_stop_loss:
                        span.set_attribute("stop_loss_unchanged", True)
                        return StopLossUpdate(
                            symbol=symbol,
                            current_price=current_price,
                            entry_price=entry_price,
                            position_size=position_size,
                            current_band=band,
                            current_profit_percentage=profit_percentage,
                            atr_value=atr_value,
                            new_stop_loss=previous_stop_loss,
                            previous_stop_loss=previous_stop_loss,
                            multiplier_used=multiplier,
                            reason="New stop loss would be higher than current"
                        )

                # Create update with new stop loss
                update = StopLossUpdate(
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=entry_price,
                    position_size=position_size,
                    current_band=band,
                    current_profit_percentage=profit_percentage,
                    atr_value=atr_value,
                    new_stop_loss=new_stop_loss,
                    previous_stop_loss=previous_stop_loss,
                    multiplier_used=multiplier,
                    reason=f"Updated based on {band.value} band"
                )

                logfire.info("Stop loss calculated", **update.model_dump())
                return update

        except Exception as e:
            logfire.error("Stop loss calculation failed", 
                         symbol=symbol,
                         error=str(e),
                         current_price=current_price,
                         entry_price=entry_price)
            raise