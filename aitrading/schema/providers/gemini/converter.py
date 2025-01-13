# aitrading/schema/providers/gemini/converter.py

from typing import Dict, Any
import logging
from .type_mapping import TYPE_MAPPING, convert_type
from .flattener import flatten_schema
from .utils import handle_array_items, handle_properties

logger = logging.getLogger(__name__)

class GeminiSchemaConverter:
    """Converter for Gemini's schema format."""

    def convert(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pydantic/OpenAPI schema to Gemini schema format."""
        #logger.debug(f"Converting schema for Gemini: {schema}")
        try:
            # Flatten schema if it has definitions
            if "$defs" in schema:
                flattened = flatten_schema(schema)
                #logger.debug(f"Flattened schema: {flattened}")
                return self._convert_schema(flattened)
            return self._convert_schema(schema)
        except Exception as e:
            logger.error(f"Error in convert: {str(e)}")
            raise

    def _convert_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a schema object to Gemini format."""
        if not isinstance(schema, dict):
            return schema

        converted = {}

        # Handle anyOf/oneOf by selecting first non-null type
        if "anyOf" in schema:
            for option in schema["anyOf"]:
                if option.get("type") != "null":
                    return self._convert_schema(option)
            return {"type": "STRING"}

        # Convert basic type if present
        if "type" in schema:
            converted["type"] = convert_type(schema["type"])

        # Handle properties for objects
        if "properties" in schema:
            converted["properties"] = handle_properties(schema["properties"], self._convert_schema)

        # Handle arrays
        if "items" in schema:
            converted["items"] = handle_array_items(schema["items"], self._convert_schema)

        # Copy required fields
        if "required" in schema:
            converted["required"] = schema["required"]

        # Copy description
        if "description" in schema:
            converted["description"] = schema["description"]

        # Handle enums
        if "enum" in schema:
            converted["enum"] = schema["enum"]

        # Ensure type is present for objects
        if "properties" in schema and "type" not in converted:
            converted["type"] = "OBJECT"

        # Ensure type is present for arrays
        if "items" in schema and "type" not in converted:
            converted["type"] = "ARRAY"

        return converted

    def validate(self, schema: Dict[str, Any]) -> bool:
        """Validate schema compatibility with Gemini."""
        if not isinstance(schema, dict):
            return False

        if "type" in schema and schema["type"].lower() not in TYPE_MAPPING:
            return False

        return True