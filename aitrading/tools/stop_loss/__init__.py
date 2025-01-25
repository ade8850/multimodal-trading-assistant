"""
Stop Loss Management Module

This module provides automated stop loss management based on ATR (Average True Range)
and profit bands. It implements a dynamic stop loss adjustment strategy that adapts
to market volatility and position performance.

The module uses a configuration-driven approach where stop loss distances are
calculated as multiples of the ATR, with multipliers that increase as the position
moves into profit, providing more room for profitable trades to develop while
maintaining protection against adverse moves.
"""

from .models import StopLossConfig, StopLossUpdate, ProfitBand
from .calculator import StopLossCalculator
from .manager import StopLossManager

__all__ = [
    'StopLossConfig',
    'StopLossUpdate',
    'ProfitBand',
    'StopLossCalculator',
    'StopLossManager'
]