import logfire
from typing import Optional


class OrderContext:
    """Manages order context in Redis."""

    def __init__(self, redis_provider, ttl_seconds: int = 2592000):  # 30 days
        """Initialize order context manager.

        Args:
            redis_provider: Redis connection provider
            ttl_seconds: Time-to-live for order context in seconds (default 30 days)
        """
        self.redis = redis_provider
        self.key_prefix = "order_context:"
        self.ttl = ttl_seconds

    def _get_key(self, order_link_id: str) -> str:
        """Get Redis key for an order."""
        return f"{self.key_prefix}{order_link_id}"

    def save_context(self, order_link_id: str, context: str) -> bool:
        """Save order context to Redis.

        Args:
            order_link_id: Unique order identifier
            context: Strategic context for the order

        Returns:
            bool: True if saved successfully
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                return False

            key = self._get_key(order_link_id)
            self.redis.client.set(
                key,
                context,
                ex=self.ttl
            )

            logfire.info("Saved order context",
                         order_link_id=order_link_id)
            return True

        except Exception as e:
            logfire.error("Failed to save order context",
                          order_link_id=order_link_id,
                          error=str(e))
            return False

    def get_context(self, order_link_id: str) -> Optional[str]:
        """Get order context from Redis.

        Args:
            order_link_id: Unique order identifier

        Returns:
            Optional[str]: Context string if found
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                return None

            key = self._get_key(order_link_id)
            context = self.redis.client.get(key)

            return context.decode('utf-8') if context else None

        except Exception as e:
            logfire.error("Failed to get order context",
                          order_link_id=order_link_id,
                          error=str(e))
            return None