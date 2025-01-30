import json
import logfire
from typing import Dict, List, Any
from openai import OpenAI
from ..base import BaseAIClient
from ....schema import SchemaConverter


class OpenAIClient(BaseAIClient):
    """Client for interacting with OpenAI's GPT-4V model."""

    def __init__(self, api_key: str):
        """Initialize the OpenAI client."""
        super().__init__(api_key)
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        logfire.instrument_openai(self.client)
        logfire.info("OpenAI client initialized")

    def generate_strategy(self, system_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using GPT-4V.
        
        This implementation processes market charts through GPT-4V's vision capabilities
        and generates a structured trading plan based on technical analysis.
        
        Args:
            system_prompt: Framework and rules for analysis
            images: Technical analysis charts in PNG format
            
        Returns:
            Complete trading plan with analysis and orders
        """
        try:

            # Process images for OpenAI's format
            formatted_images = self._format_images(images)

            # Generate schema
            from aitrading.models import PlanResponse
            schema = PlanResponse.model_json_schema()

            # Convert schema for OpenAI
            try:
                openai_schema = SchemaConverter.convert(schema, "openai")
            except Exception as e:
                logfire.exception(f"Error converting schema: {str(e)}")
                raise

            # Add schema requirements to system prompt
            schema_requirements = f"""
Your response must be a valid JSON object matching the following schema exactly:
{json.dumps(openai_schema, indent=2)}
            """

            final_system_prompt = f"{system_prompt}\n\n{schema_requirements}"

            # Prepare messages for GPT-4V
            messages = [
                {"role": "system", "content": final_system_prompt},
                {
                    "role": "user",
                    "content": [
                        *formatted_images
                    ]
                }
            ]

            # Generate content with structured output
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4096,
                temperature=0,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logfire.exception(str(e))
                raise ValueError(f"Invalid JSON response from OpenAI: {str(e)}")

            # Validate response structure and content
            if not self._validate_response(result):
                raise ValueError("Response validation failed")

            # Ensure order IDs are progressive
            orders = result["plan"].get("orders", [])
            for i, order in enumerate(orders, 1):
                if order.get("id") != i:
                    order["id"] = i

            return result

        except Exception as e:
            raise Exception(f"Error generating strategy with OpenAI: {str(e)}")

    def _format_images(self, images: List[bytes]) -> List[Dict]:
        """Convert images to OpenAI's expected format.
        
        Args:
            images: List of image bytes
            
        Returns:
            List of formatted image objects for OpenAI's API
        """
        import base64
        return [{
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64.b64encode(img).decode('utf-8')}"
            }
        } for img in images]
