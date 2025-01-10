# aitrading/schema/__init__.py

from .converter import SchemaConverter
from .providers.gemini import GeminiSchemaConverter
from .providers.anthropic import AnthropicSchemaConverter
from .providers.openai import OpenAISchemaConverter
from .exceptions import (
    SchemaConverterError,
    UnsupportedProviderError,
    SchemaValidationError,
    ConversionError
)

# Register available converters
SchemaConverter.register_converter("gemini", GeminiSchemaConverter)
SchemaConverter.register_converter("anthropic", AnthropicSchemaConverter)
SchemaConverter.register_converter("openai", OpenAISchemaConverter)  # Added OpenAI registration

__all__ = [
    'SchemaConverter',
    'SchemaConverterError',
    'UnsupportedProviderError',
    'SchemaValidationError',
    'ConversionError'
]