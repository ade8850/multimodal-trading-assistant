# aitrading/schema/providers/gemini/utils.py

from typing import Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)


def handle_properties(
        properties: Dict[str, Any],
        convert_func: Callable[[Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """Handle object properties conversion."""
    converted = {}

    for key, value in properties.items():
        # Handle null/optional fields
        if isinstance(value, dict) and "anyOf" in value:
            non_null_type = next(
                (opt for opt in value["anyOf"] if opt.get("type") != "null"),
                {"type": "string"}  # default to string if all null
            )
            converted[key] = convert_func(non_null_type)
        else:
            converted[key] = convert_func(value)

    return converted


def handle_array_items(
        items: Dict[str, Any],
        convert_func: Callable[[Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """Handle array items conversion."""
    return convert_func(items)