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
            
            # Fix orders type field: convert 'buy' to 'long' and 'sell' to 'short'
            if 'orders' in plan and isinstance(plan['orders'], list):
                for order in plan['orders']:
                    if isinstance(order, dict):
                        # Fix outer type field
                        if 'type' in order:
                            # Convert buy/sell to long/short
                            if order['type'].lower() == 'buy':
                                order['type'] = 'long'
                            elif order['type'].lower() == 'sell':
                                order['type'] = 'short'
                        
                        # Ensure reduce_only orders have symbol specified
                        if order.get('reduce_only', False) and 'symbol' not in order:
                            # If we have parameters with symbol, use that
                            if 'parameters' in plan and 'symbol' in plan['parameters']:
                                order['symbol'] = plan['parameters']['symbol']
                        
                        # Check and fix nested order object as well
                        if 'order' in order and isinstance(order['order'], dict):
                            nested_order = order['order']
                            # Fix type in nested order object
                            if 'type' in nested_order:
                                # Map invalid order types to valid ones
                                type_mapping = {
                                    'buy': 'market',
                                    'sell': 'market',
                                    'long': 'market',
                                    'short': 'market'
                                }
                                
                                if nested_order['type'].lower() in type_mapping:
                                    nested_order['type'] = type_mapping[nested_order['type'].lower()]
                                    
                            # Map side in nested order to make sure it's Buy/Sell (not buy/sell)
                            if 'side' in nested_order:
                                if nested_order['side'].lower() == 'buy':
                                    nested_order['side'] = 'Buy'
                                elif nested_order['side'].lower() == 'sell':
                                    nested_order['side'] = 'Sell'

            # Validate using Pydantic model
            from ...models import TradingPlan
            validated_plan = TradingPlan(**plan)
            response['plan'] = validated_plan.model_dump()

            return True

        except Exception as e:
            raise ValueError(f"Response validation failed: {str(e)}")