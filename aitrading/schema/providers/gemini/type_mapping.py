# aitrading/schema/providers/gemini/type_mapping.py

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Mapping of JSON Schema types to Gemini types
TYPE_MAPPING = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
    "null": "STRING",  # Mapping null to STRING per Gemini
}


def convert_type(original_type: str) -> str:
    """Convert JSON Schema type to Gemini type."""
    original_type = original_type.lower()
    if original_type not in TYPE_MAPPING:
        logger.error(f"Unsupported type: {original_type}")
        raise ValueError(f"Unsupported type: {original_type}")

    return TYPE_MAPPING[original_type]