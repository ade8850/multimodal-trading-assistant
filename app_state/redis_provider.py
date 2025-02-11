import redis
from typing import Optional
import os
import logfire

class RedisProvider:
    """Simple Redis provider for UI state persistence."""

    def __init__(self):
        """Initialize Redis connection from environment variables."""
        self.enabled = True
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.db = int(os.getenv("REDIS_DB", 0))
        self.password = os.getenv("REDIS_PASSWORD", "")
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client, creating it if necessary."""
        if self._client is None:
            try:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True
                )
                logfire.info("Redis connection established",
                           host=self.host,
                           port=self.port,
                           db=self.db)
            except Exception as e:
                logfire.error("Failed to connect to Redis",
                          error=str(e),
                          host=self.host,
                          port=self.port)
                self.enabled = False
                return None

        return self._client

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