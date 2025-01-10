# aitrading/schema/providers/gemini/flattener.py

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def flatten_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten schema by resolving all references."""
    flattened = schema.copy()
    definitions = schema.get("$defs", {})

    def resolve_refs(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolve schema references."""
        if not isinstance(obj, dict):
            return obj

        if "$ref" in obj:
            ref_path = obj["$ref"].split("/")
            if ref_path[0] == "#" and ref_path[1] == "$defs":
                def_name = ref_path[-1]
                if def_name in definitions:
                    return resolve_refs(definitions[def_name])
                else:
                    logger.error(f"Reference not found: {def_name}")
                    raise ValueError(f"Reference not found: {def_name}")

        result = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                result[key] = resolve_refs(value)
            elif isinstance(value, list):
                result[key] = [
                    resolve_refs(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    # Flatten main schema
    flattened = resolve_refs(flattened)

    # Remove definitions after flattening
    if "$defs" in flattened:
        del flattened["$defs"]

    return flattened