# aitrading/schema/providers/openai.py

from typing import Dict, Any
from ..converter import BaseSchemaConverter
from ..exceptions import ConversionError
from logging import getLogger

logger = getLogger(__name__)


class OpenAISchemaConverter(BaseSchemaConverter):
    """Converter for OpenAI's schema format.

    OpenAI accepts JSON Schema format with some specific requirements:
    1. It must be a valid JSON Schema
    2. It supports a subset of JSON Schema features
    3. Has specific handling for function calling schemas
    """

    # Types supported by OpenAI's function schema
    SUPPORTED_TYPES = {
        "string", "number", "integer", "boolean", "array", "object", "null"
    }

    def __init__(self):
        """Initialize the converter."""
        self._original_schema = None
        self._definitions = {}

    def convert(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert schema to OpenAI's expected format."""
        try:
            # Store original schema for reference resolution
            self._original_schema = schema.copy()

            # Extract and store definitions
            self._definitions = schema.get("$defs", {})

            # Work with a copy to avoid modifying original
            converted = self._convert_schema(schema.copy())
            logger.debug(f"Converted schema for OpenAI: {converted}")
            return converted
        except Exception as e:
            logger.error(f"Error converting schema for OpenAI: {e}")
            raise ConversionError(str(e), schema, "openai")
        finally:
            # Clean up
            self._original_schema = None
            self._definitions = {}

    def validate(self, schema: Dict[str, Any]) -> bool:
        """Validate schema compatibility with OpenAI."""
        if not isinstance(schema, dict):
            return False

        # Validate type if present
        if "type" in schema:
            schema_type = schema["type"].lower()
            if schema_type not in self.SUPPORTED_TYPES:
                return False

        # Validate properties if present
        if "properties" in schema and not isinstance(schema["properties"], dict):
            return False

        # Validate items for arrays
        if schema.get("type") == "array" and "items" in schema:
            if not isinstance(schema["items"], dict):
                return False

        return True

    def _convert_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and normalize schema to OpenAI's expected format."""
        converted = {}

        # Handle refs and definitions
        if "$ref" in schema:
            resolved = self._resolve_ref(schema)
            return self._convert_schema(resolved)

        # Convert type
        if "type" in schema:
            original_type = schema["type"].lower()
            if original_type not in self.SUPPORTED_TYPES:
                raise ConversionError(
                    f"Unsupported type: {original_type}",
                    schema,
                    "openai"
                )
            converted["type"] = original_type

        # Convert properties recursively
        if "properties" in schema:
            converted["properties"] = {}
            for key, value in schema["properties"].items():
                # Handle null/optional fields
                if isinstance(value, dict) and "anyOf" in value:
                    non_null_type = next(
                        (opt for opt in value["anyOf"] if opt.get("type") != "null"),
                        {"type": "string"}  # default to string if all null
                    )
                    converted["properties"][key] = self._convert_schema(non_null_type)
                else:
                    converted["properties"][key] = self._convert_schema(value)

        # Convert array items
        if "items" in schema:
            converted["items"] = self._convert_schema(schema["items"])

        # Handle enums
        if "enum" in schema:
            converted["enum"] = schema["enum"]

        # Keep standard JSON Schema fields that OpenAI supports
        supported_fields = [
            "required", "description", "title",
            "minimum", "maximum", "minItems", "maxItems",
            "pattern", "format"
        ]

        for field in supported_fields:
            if field in schema:
                converted[field] = schema[field]

        # Ensure type is present for objects with properties
        if "properties" in converted and "type" not in converted:
            converted["type"] = "object"

        # Ensure type is present for arrays with items
        if "items" in converted and "type" not in converted:
            converted["type"] = "array"

        # Clean up OpenAI-specific adjustments
        self._cleanup_for_openai(converted)

        return converted

    def _cleanup_for_openai(self, schema: Dict[str, Any]) -> None:
        """Apply OpenAI-specific cleanup and adjustments."""
        # Remove unsupported formats
        if "format" in schema:
            supported_formats = ["date-time", "date", "time", "email", "uri"]
            if schema["format"] not in supported_formats:
                del schema["format"]

        # Ensure number types have appropriate constraints
        if schema.get("type") == "number":
            if "minimum" in schema and isinstance(schema["minimum"], str):
                schema["minimum"] = float(schema["minimum"])
            if "maximum" in schema and isinstance(schema["maximum"], str):
                schema["maximum"] = float(schema["maximum"])

        # Remove empty required arrays
        if "required" in schema and not schema["required"]:
            del schema["required"]

        # Clean up any remaining OpenAI-incompatible fields
        fields_to_remove = ["$defs", "definitions", "anyOf", "allOf", "oneOf", "not"]
        for field in fields_to_remove:
            if field in schema:
                del schema[field]

    def _resolve_ref(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve JSON Schema $ref."""
        if "$ref" not in schema:
            return schema

        # Currently handles only local refs
        ref_path = schema["$ref"]
        if not ref_path.startswith("#/"):
            raise ConversionError(
                f"Only local refs supported, got: {ref_path}",
                schema,
                "openai"
            )

        # Parse ref path
        path_parts = ref_path.split("/")[1:]

        # Start from definitions if ref points there
        if path_parts[0] == "$defs":
            current = self._definitions
            path_parts = path_parts[1:]  # Skip the "$defs" part
        else:
            current = self._original_schema

        # Navigate through the path
        for part in path_parts:
            if part not in current:
                raise ConversionError(
                    f"Invalid ref path: {ref_path}, part '{part}' not found",
                    schema,
                    "openai"
                )
            current = current[part]

        return current