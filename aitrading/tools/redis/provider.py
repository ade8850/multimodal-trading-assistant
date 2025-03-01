from typing import Optional, Dict, Any
import redis
from redis.client import Redis
import logfire


class RedisProvider:
    """Provider for Redis connections."""

    def __init__(
            self,
            enabled: bool = False,
            host: str = "localhost",
            port: int = 6379,
            db: int = 0,
            password: Optional[str] = None,
            ssl: bool = False,
            key_prefix: str = "trading:",
            max_stream_length: int = 1000
    ):
        """Initialize Redis provider.

        Args:
            enabled: Whether Redis is enabled
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Optional Redis password
            ssl: Whether to use SSL
            key_prefix: Prefix for all Redis keys
            max_stream_length: Default maximum length for Redis streams
        """
        self.enabled = enabled
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.ssl = ssl
        self.key_prefix = key_prefix
        self.max_stream_length = max_stream_length
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Optional[Redis]:
        """Get Redis client, creating it if necessary."""
        if not self.enabled:
            return None

        if self._client is None:
            try:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    ssl=self.ssl,
                    decode_responses=True
                )
                logfire.info("Redis connection established",
                             host=self.host,
                             port=self.port,
                             db=self.db,
                             ssl=self.ssl)
            except Exception as e:
                logfire.error("Failed to connect to Redis",
                              error=str(e),
                              host=self.host,
                              port=self.port)
                raise

        return self._client

    def get_prefixed_key(self, key: str) -> str:
        """Get key with prefix applied."""
        return f"{self.key_prefix}{key}"

    def add_to_stream(self, stream_name: str, data: Dict[str, str], max_len: Optional[int] = None) -> Optional[str]:
        """Add data to a Redis stream.
        
        Args:
            stream_name: Name of the stream (without prefix)
            data: Dictionary of field-value pairs to add to the stream
            max_len: Maximum length of the stream (defaults to self.max_stream_length)
            
        Returns:
            Optional[str]: Message ID if successful, None otherwise
        """
        try:
            if not self.enabled or not self.client:
                logfire.info("Redis not enabled, stream entry not added", 
                             stream=stream_name)
                return None
                
            stream_key = self.get_prefixed_key(stream_name)
            max_length = max_len if max_len is not None else self.max_stream_length
            
            # Add to stream with MAXLEN trimming
            message_id = self.client.xadd(
                name=stream_key,
                fields=data,
                maxlen=max_length,
                approximate=True
            )
            
            logfire.info("Added entry to Redis stream",
                         stream=stream_name,
                         message_id=message_id)
                         
            return message_id
            
        except Exception as e:
            logfire.error("Failed to add to Redis stream",
                          stream=stream_name,
                          error=str(e))
            return None

    def close(self) -> None:
        """Close Redis connection if open."""
        if self._client is not None:
            try:
                self._client.close()
                logfire.info("Redis connection closed")
            except Exception as e:
                logfire.error("Error closing Redis connection",
                              error=str(e))
            finally:
                self._client = None

    def __enter__(self) -> 'RedisProvider':
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and ensure connection is closed."""
        self.close()

    def __del__(self) -> None:
        """Ensure connection is closed when object is garbage collected."""
        self.close()