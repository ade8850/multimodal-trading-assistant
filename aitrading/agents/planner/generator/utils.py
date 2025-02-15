from typing import Dict, Any
from ....tools.volatility.models import TimeframeVolatility


def convert_pydantic_to_dict(obj: Any) -> Any:
    """Convert Pydantic objects to plain dictionaries recursively."""
    # Special case for TimeframeVolatility: pass it through unchanged
    if isinstance(obj, TimeframeVolatility):
        return obj

    if hasattr(obj, 'model_dump'):
        obj_dict = obj.model_dump()
    elif hasattr(obj, 'dict'):
        obj_dict = obj.dict()
    else:
        return obj

    for key, value in obj_dict.items():
        if isinstance(value, TimeframeVolatility):
            obj_dict[key] = value
        elif hasattr(value, 'model_dump') or hasattr(value, 'dict'):
            obj_dict[key] = convert_pydantic_to_dict(value)
        elif isinstance(value, dict):
            obj_dict[key] = {k: convert_pydantic_to_dict(v) for k, v in value.items()}
        elif isinstance(value, list):
            obj_dict[key] = [convert_pydantic_to_dict(item) for item in value]
        elif isinstance(value, (int, float, str, bool, type(None))):
            obj_dict[key] = value
        else:
            obj_dict[key] = str(value)
    return obj_dict