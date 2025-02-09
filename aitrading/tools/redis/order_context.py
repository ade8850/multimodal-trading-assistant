import json
import logfire
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


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

    def save_context(self, order_link_id: str, context: BaseModel) -> bool:
        """Save order context to Redis.

        Args:
            order_link_id: Unique order identifier
            context: Strategic context object (must be Pydantic model)

        Returns:
            bool: True if saved successfully
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                logfire.info("Redis not enabled, context not saved",
                             order_link_id=order_link_id)
                return True

            key = self._get_key(order_link_id)

            # Convert context to dictionary and add metadata
            context_data = {
                "model": context.__class__.__name__,
                "data": context.model_dump(),
                "saved_at": datetime.utcnow().isoformat()
            }

            # Serialize to JSON
            serialized = json.dumps(context_data)

            # Save to Redis with TTL
            success = self.redis.client.set(
                name=key,
                value=serialized,
                ex=self.ttl
            )

            if success:
                logfire.info("Saved order context",
                             order_link_id=order_link_id,
                             model=context_data["model"])
            else:
                logfire.error("Failed to save context to Redis",
                              order_link_id=order_link_id)

            return bool(success)

        except Exception as e:
            logfire.error("Failed to save order context",
                          order_link_id=order_link_id,
                          error=str(e))
            return False

    def get_context(self, order_link_id: str) -> Optional[Dict[str, Any]]:
        """Get order context from Redis.

        Args:
            order_link_id: Unique order identifier

        Returns:
            Optional[Dict[str, Any]]: Context data if found
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                logfire.info("Redis not enabled, cannot retrieve context",
                             order_link_id=order_link_id)
                return None

            key = self._get_key(order_link_id)
            raw_data = self.redis.client.get(key)

            if not raw_data:
                logfire.debug("No context found",
                              order_link_id=order_link_id)
                return None

            # Parse JSON data
            context_data = json.loads(raw_data.decode('utf-8'))

            logfire.info("Retrieved order context",
                         order_link_id=order_link_id,
                         model=context_data.get("model"))

            return context_data

        except Exception as e:
            logfire.error("Failed to get order context",
                          order_link_id=order_link_id,
                          error=str(e))
            return None

    def delete_context(self, order_link_id: str) -> bool:
        """Delete order context from Redis.

        Args:
            order_link_id: Unique order identifier

        Returns:
            bool: True if deleted successfully
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                return False

            key = self._get_key(order_link_id)
            success = self.redis.client.delete(key)

            if success:
                logfire.info("Deleted order context",
                             order_link_id=order_link_id)
            else:
                logfire.debug("No context to delete",
                              order_link_id=order_link_id)

            return bool(success)

        except Exception as e:
            logfire.error("Failed to delete order context",
                          order_link_id=order_link_id,
                          error=str(e))
            return False