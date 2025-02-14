"""Base classes for AI provider clients."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any

class BaseAIClient(ABC):
    """Base interface for AI model clients."""

    def __init__(self, api_key: str):
        """Initialize the AI client with API key."""
        self.api_key = api_key

    @abstractmethod
    def generate_strategy(self, system_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using the AI model.

        Args:
            system_prompt (str): Framework and rules for analysis
            images (List[bytes]): Chart images in PNG format

        Returns:
            Dict[str, Any]: Plan response containing:
                - 'plan': Complete trading plan with unique ID and session ID
                - Orders list with progressive numeric IDs
                - Analysis and rationale
        """
        pass

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """Validate response structure and content."""
        try:
            if not isinstance(response, dict):
                raise ValueError("Response must be a dictionary")

            if 'plan' not in response:
                raise ValueError("Response missing 'plan' key")

            # Pre-process the response
            plan = response['plan']

            # Convert analysis object to string if needed
            if isinstance(plan.get('analysis'), dict):
                market_context = plan['analysis'].get('market_context', '')
                reasoning = plan.get('reasoning', '')
                plan['analysis'] = f"{market_context}\n\n{reasoning}"

            # Add defaults if missing
            if 'created_at' not in plan:
                plan['created_at'] = datetime.utcnow().isoformat()

            # Validate using Pydantic model
            from ...models import TradingPlan
            validated_plan = TradingPlan(**plan)
            response['plan'] = validated_plan.model_dump()

            return True

        except Exception as e:
            raise ValueError(f"Response validation failed: {str(e)}")