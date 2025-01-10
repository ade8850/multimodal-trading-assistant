# aitrading/schema/providers/anthropic/client.py

from typing import Dict, Any
from ..converter import BaseSchemaConverter
from ..exceptions import ConversionError
from logging import getLogger

logger = getLogger(__name__)


class AnthropicSchemaConverter(BaseSchemaConverter):
    """Converter for Anthropic's schema format."""

    SUPPORTED_TYPES = {
        "string", "number", "integer", "boolean", "array", "object", "null"
    }

    def __init__(self):
        """Initialize the converter."""
        self._original_schema = None
        self._definitions = {}

    def convert(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert schema to Anthropic format (JSON Schema standard)."""
        try:
            # Store original schema for reference resolution
            self._original_schema = schema.copy()

            # Extract and store definitions
            self._definitions = schema.get("$defs", {})

            # Work with a copy to avoid modifying original
            converted = self._convert_schema(schema.copy())
            logger.debug(f"Converted schema for Anthropic: {converted}")
            return converted
        except Exception as e:
            logger.error(f"Error converting schema for Anthropic: {e}")
            raise ConversionError(str(e), schema, "anthropic")
        finally:
            # Clean up
            self._original_schema = None
            self._definitions = {}

    def validate(self, schema: Dict[str, Any]) -> bool:
        """Basic validation for JSON Schema compatibility."""
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

        # Validate items if array
        if schema.get("type") == "array" and "items" in schema:
            if not isinstance(schema["items"], dict):
                return False

        return True

    def _convert_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and normalize schema recursively."""
        if not isinstance(schema, dict):
            return schema

        # Handle refs first
        if "$ref" in schema:
            resolved = self._resolve_ref(schema)
            return self._convert_schema(resolved)

        converted = {}

        # Convert type
        if "type" in schema:
            original_type = schema["type"].lower()
            if original_type not in self.SUPPORTED_TYPES:
                raise ConversionError(
                    f"Unsupported type: {original_type}",
                    schema,
                    "anthropic"
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

        # Keep standard JSON Schema fields
        standard_fields = [
            "required", "description", "title", "enum",
            "minimum", "maximum", "minItems", "maxItems",
            "pattern", "format", "default", "examples"
        ]

        for field in standard_fields:
            if field in schema:
                converted[field] = schema[field]

        # Ensure type is present for objects
        if "properties" in schema and "type" not in converted:
            converted["type"] = "object"

        # Ensure type is present for arrays
        if "items" in schema and "type" not in converted:
            converted["type"] = "array"

        return converted

    def _resolve_ref(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve JSON Schema $ref."""
        if "$ref" not in schema:
            return schema

        ref_path = schema["$ref"]
        if not ref_path.startswith("#/"):
            raise ConversionError(
                f"Only local refs supported, got: {ref_path}",
                schema,
                "anthropic"
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
                    "anthropic"
                )
            current = current[part]

        return current