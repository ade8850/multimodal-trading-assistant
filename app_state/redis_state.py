from typing import Dict, Any, Optional
import json
import logfire
from aitrading.tools.redis.provider import RedisProvider


class RedisState:
    """Manages interface state persistence in Redis."""

    def __init__(self, redis_provider: RedisProvider):
        """Initialize with Redis provider."""
        self.redis = redis_provider
        self.state_key = "streamlit:last_state"

    def save_state(self, state: Dict[str, Any]) -> bool:
        """Save current interface state.

        Args:
            state: Dictionary containing the current interface state
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                logfire.info("Redis not enabled, state not saved")
                return False

            data = json.dumps(state)
            success = self.redis.client.set(self.state_key, data)

            if success:
                logfire.info("Saved interface state", state=state)
            else:
                logfire.error("Failed to save interface state")

            return bool(success)

        except Exception as e:
            logfire.error("Error saving state", error=str(e))
            return False

    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load last saved interface state.

        Returns:
            Dictionary containing the last saved state if found, None otherwise
        """
        try:
            if not self.redis.enabled or not self.redis.client:
                logfire.info("Redis not enabled, cannot load state")
                return None

            data = self.redis.client.get(self.state_key)

            if not data:
                logfire.debug("No saved state found")
                return None

            state = json.loads(data)
            logfire.info("Loaded interface state", state=state)
            return state

        except Exception as e:
            logfire.error("Error loading state", error=str(e))
            return None