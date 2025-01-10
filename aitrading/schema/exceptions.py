# aitrading/schema/exceptions.py

class SchemaConverterError(Exception):
    """Base exception for schema conversion errors."""
    pass

class UnsupportedProviderError(SchemaConverterError):
    """Raised when trying to use an unsupported provider."""
    pass

class SchemaValidationError(SchemaConverterError):
    """Raised when the input schema is invalid."""
    pass

class ConversionError(SchemaConverterError):
    """Raised when schema conversion fails."""
    def __init__(self, message: str, original_schema: dict, provider: str):
        self.original_schema = original_schema
        self.provider = provider
        super().__init__(f"Error converting schema for {provider}: {message}")