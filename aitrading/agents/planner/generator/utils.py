from typing import Dict, Any
from datetime import datetime, date, time
from ....tools.volatility.models import TimeframeVolatility


def convert_pydantic_to_dict(obj: Any) -> Any:
    """Convert Pydantic objects to plain dictionaries recursively.
    
    Handles special cases like datetime objects for JSON serialization.
    """
    # Handle None
    if obj is None:
        return None
        
    # Handle datetime objects
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
        
    # Special case for TimeframeVolatility: pass it through unchanged
    if isinstance(obj, TimeframeVolatility):
        return obj

    # Handle Pydantic models
    if hasattr(obj, 'model_dump'):
        obj_dict = obj.model_dump()
    elif hasattr(obj, 'dict'):
        obj_dict = obj.dict()
    # Handle basic types
    elif isinstance(obj, (int, float, str, bool)):
        return obj
    # Handle non-pydantic objects
    elif not isinstance(obj, dict):
        return str(obj)
    else:
        obj_dict = obj

    # Process dictionary recursively
    result = {}
    for key, value in obj_dict.items():
        if isinstance(value, TimeframeVolatility):
            result[key] = value
        elif isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        elif hasattr(value, 'model_dump') or hasattr(value, 'dict'):
            result[key] = convert_pydantic_to_dict(value)
        elif isinstance(value, dict):
            result[key] = {k: convert_pydantic_to_dict(v) for k, v in value.items()}
        elif isinstance(value, list):
            result[key] = [convert_pydantic_to_dict(item) for item in value]
        elif isinstance(value, (int, float, str, bool, type(None))):
            result[key] = value
        else:
            result[key] = str(value)
    return result