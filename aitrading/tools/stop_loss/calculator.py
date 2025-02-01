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
        current_stop_loss: float,
        position_type: str
    ) -> Tuple[ProfitBand, float]:
        """Determine if the position is currently in profit based on the stop loss level."""

        if position_type.lower() == 'buy':
            if entry_price < current_stop_loss:
                return ProfitBand.FIRST_PROFIT, self.config.in_profit_multiplier
            else:
                return ProfitBand.INITIAL, self.config.initial_multiplier
        else:  # sell
            if entry_price > current_stop_loss:
                return ProfitBand.FIRST_PROFIT, self.config.in_profit_multiplier
            else:
                return ProfitBand.INITIAL, self.config.initial_multiplier

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
            position_type: Either 'buy' or 'sell' (from Bybit API)
            atr_value: Current ATR value
            previous_stop_loss: Current active stop loss level
            
        Returns:
            StopLossUpdate object with new stop loss details
        """
        try:
            with logfire.span("stop_loss_calculation") as span:
                # Get profit band and multiplier
                band, multiplier = self.calculate_profit_band(
                    entry_price, previous_stop_loss, position_type
                )

                # Add detailed logging
                logfire.info("Stop loss calculation parameters", **{
                    "symbol": symbol,
                    "current_price": current_price,
                    "entry_price": entry_price,
                    "position_type": position_type,
                    "atr_value": atr_value,
                    "band": band,
                    "multiplier": multiplier,
                    "previous_stop_loss": previous_stop_loss
                })

                # Calculate new stop loss level
                atr_distance = atr_value * multiplier
                logfire.info("ATR distance calculated", **{
                    "atr_value": atr_value,
                    "multiplier": multiplier,
                    "atr_distance": atr_distance
                })

                # Determine if this is a long (buy) or short (sell) position
                is_long = position_type.lower() == 'buy'
                logfire.info("Position type determined", **{
                    "position_type": position_type,
                    "is_long": is_long,
                    "calculation_type": "long" if is_long else "short"
                })

                if is_long:
                    new_stop_loss = current_price - atr_distance
                    logfire.info("Long position stop loss calculated", **{
                        "new_stop_loss": new_stop_loss,
                        "calculation": f"{current_price} - {atr_distance} = {new_stop_loss}"
                    })

                    # For long positions, ensure new stop loss is higher than previous
                    if previous_stop_loss and new_stop_loss <= previous_stop_loss:
                        logfire.info("Stop loss movement inhibited", **{
                            "reason": "New stop loss would decrease for long position",
                            "position_type": "buy",
                            "new_stop_loss": new_stop_loss,
                            "previous_stop_loss": previous_stop_loss,
                            "difference": new_stop_loss - previous_stop_loss
                        })
                        return StopLossUpdate(
                            symbol=symbol,
                            current_price=current_price,
                            entry_price=entry_price,
                            position_size=position_size,
                            current_band=band,
                            atr_value=atr_value,
                            new_stop_loss=previous_stop_loss,
                            previous_stop_loss=previous_stop_loss,
                            multiplier_used=multiplier,
                            reason="Stop loss cannot decrease for long positions"
                        )
                else:  # short position
                    new_stop_loss = current_price + atr_distance
                    logfire.info("Short position stop loss calculated", **{
                        "new_stop_loss": new_stop_loss,
                        "calculation": f"{current_price} + {atr_distance} = {new_stop_loss}"
                    })

                    # For short positions, ensure new stop loss is lower than previous
                    if previous_stop_loss and new_stop_loss >= previous_stop_loss:
                        logfire.info("Stop loss movement inhibited", **{
                            "reason": "New stop loss would increase for short position",
                            "position_type": "sell",
                            "new_stop_loss": new_stop_loss,
                            "previous_stop_loss": previous_stop_loss,
                            "difference": new_stop_loss - previous_stop_loss
                        })
                        return StopLossUpdate(
                            symbol=symbol,
                            current_price=current_price,
                            entry_price=entry_price,
                            position_size=position_size,
                            current_band=band,
                            atr_value=atr_value,
                            new_stop_loss=previous_stop_loss,
                            previous_stop_loss=previous_stop_loss,
                            multiplier_used=multiplier,
                            reason="Stop loss cannot increase for short positions"
                        )

                # Create update with new stop loss
                update = StopLossUpdate(
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=entry_price,
                    position_size=position_size,
                    current_band=band,
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
