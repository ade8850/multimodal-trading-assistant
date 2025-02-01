import json
from typing import Dict, List, Any
from google import genai
from google.genai import types
import logfire

from ..base import BaseAIClient
from ....schema import SchemaConverter

class GeminiClient(BaseAIClient):
    """Client for interacting with Google's Gemini model."""

    def __init__(self, api_key: str):
        """Initialize the Gemini client."""
        super().__init__(api_key)
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.0-flash-exp'
        logfire.info("Gemini client initialized")

    def generate_strategy(self, system_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using Gemini."""
        try:
            logfire.info("Starting plan generation with Gemini")

            # Process images
            gemini_images = [
                types.Part.from_bytes(img, 'image/png') for img in images
            ]
            logfire.debug(f"Processed {len(gemini_images)} images")

            # Generate schema
            from ....models import PlanResponse
            schema = PlanResponse.model_json_schema()

            try:
                gemini_schema = SchemaConverter.convert(schema, "gemini")
                logfire.debug(f"Converted Gemini schema", schema=gemini_schema)
            except Exception as e:
                logfire.exception(f"Error converting schema: {str(e)}")
                raise

            # Generate content
            content_parts = [
                types.Part.from_text(text=system_prompt),
                *gemini_images
            ]
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=gemini_schema,
                    #system_instruction=system_prompt,
                    temperature=0
                )
            )

            logfire.debug("Raw response text", text=response.text)

            try:
                result = json.loads(response.text)
            except json.JSONDecodeError as e:
                logfire.error(f"JSON parsing error: {str(e)}")
                raise ValueError(f"Invalid JSON response from Gemini: {str(e)}")

            if not self._validate_response(result):
                raise ValueError("Response validation failed")

            # Ensure order IDs are progressive
            orders = result["plan"].get("orders", [])
            for i, order in enumerate(orders, 1):
                if order.get("id") != i:
                    order["id"] = i

            logfire.info("Successfully generated and validated plan", tags=["gemini"])
            return result

        except Exception as e:
            raise Exception(f"Error generating strategy with Gemini: {str(e)}")
