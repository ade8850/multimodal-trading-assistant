"""Generator package for trading plan generation.

This package contains the components responsible for generating trading plans using AI models.
It includes budget management, position analysis, order processing and template handling.
"""

from .base import PlanGenerator
from .utils import convert_pydantic_to_dict

__all__ = [
    'PlanGenerator',
    'convert_pydantic_to_dict'
]