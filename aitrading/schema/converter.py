# aitrading/schema/converter.py

from typing import Dict, Type, Any
from abc import ABC, abstractmethod
from logging import getLogger
from .exceptions import UnsupportedProviderError, SchemaValidationError

logger = getLogger(__name__)


class BaseSchemaConverter(ABC):
    """Base class for schema converters."""

    @abstractmethod
    def convert(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the schema to provider-specific format.

        Args:
            schema: The input schema in common format

        Returns:
            The converted schema in provider-specific format

        Raises:
            ConversionError: If conversion fails
            SchemaValidationError: If input schema is invalid
        """
        pass

    @abstractmethod
    def validate(self, schema: Dict[str, Any]) -> bool:
        """Validate that the schema is compatible with this converter.

        Args:
            schema: The schema to validate

        Returns:
            True if schema is valid, False otherwise
        """
        pass


class SchemaConverter:
    """Main schema converter that delegates to specific providers."""

    _converters: Dict[str, Type[BaseSchemaConverter]] = {}

    @classmethod
    def register_converter(cls, provider: str, converter: Type[BaseSchemaConverter]) -> None:
        """Register a new converter for a provider.

        Args:
            provider: Provider name (e.g. "gemini", "anthropic")
            converter: Converter class to register
        """
        cls._converters[provider.lower()] = converter
        logger.debug(f"Registered schema converter for provider: {provider}")

    @classmethod
    def convert(cls, schema: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """Convert schema to specified provider format.

        Args:
            schema: The input schema to convert
            provider: Target provider name

        Returns:
            Converted schema

        Raises:
            UnsupportedProviderError: If provider not registered
            SchemaValidationError: If schema invalid
            ConversionError: If conversion fails
        """
        provider = provider.lower()
        converter_class = cls._converters.get(provider)

        if not converter_class:
            raise UnsupportedProviderError(f"No converter registered for provider: {provider}")

        converter = converter_class()
        if not converter.validate(schema):
            raise SchemaValidationError(f"Invalid schema for provider: {provider}")

        logger.debug(f"Converting schema for provider: {provider}")
        return converter.convert(schema)