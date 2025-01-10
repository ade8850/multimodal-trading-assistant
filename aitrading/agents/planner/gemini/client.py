# aitrading/agents/planner/gemini/client.py

import json
import logging
from typing import Dict, List, Any
from google import genai
from google.genai import types

from ..base import BaseAIClient
from ....schema import SchemaConverter
from rich.console import Console

console = Console()


class GeminiClient(BaseAIClient):
    """Client for interacting with Google's Gemini model."""

    def __init__(self, api_key: str):
        """Initialize the Gemini client."""
        super().__init__(api_key)
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.0-flash-exp'
        logging.info("Gemini client initialized")

    def generate_strategy(self, system_prompt: str, user_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using Gemini."""
        try:
            console.print()
            console.print("Starting plan generation with Gemini", style="bold green")

            # Process images
            gemini_images = [
                types.Part.from_bytes(img, 'image/png') for img in images
            ]
            logging.debug(f"Processed {len(gemini_images)} images")

            # Generate schema
            from ....models import PlanResponse
            schema = PlanResponse.model_json_schema()

            # Convertiamo lo schema per Gemini
            try:
                gemini_schema = SchemaConverter.convert(schema, "gemini")
                console.print(gemini_schema)
                logging.debug(f"Converted Gemini schema: {gemini_schema}")
            except Exception as e:
                logging.error(f"Error converting schema: {str(e)}")
                raise


            # Generate content
            response = self.client.models.generate_content(
                model=self.model,
                contents=[*gemini_images, types.Part.from_text(user_prompt)],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=gemini_schema,
                    system_instruction=system_prompt,
                    temperature=0.1
                )
            )

            console.print()
            console.print("Raw response text: ", response.text, style="grey37")

            try:
                result = json.loads(response.text)
                logging.debug(f"Parsed JSON result: {json.dumps(result, indent=2)[:500]}...")
            except json.JSONDecodeError as e:
                logging.error(f"JSON parsing error: {str(e)}")
                logging.error(f"Failed to parse response text: {response.text}")
                raise ValueError(f"Invalid JSON response from Gemini: {str(e)}")

            # Ensure IDs match
            if not self._validate_response(result):
                raise ValueError("Response validation failed")


            # Ensure order IDs are progressive
            orders = result["plan"].get("orders", [])
            for i, order in enumerate(orders, 1):
                if order.get("id") != i:
                    console.print(f"[yellow]Fixing order ID from {order.get('id')} to {i}[/yellow]")
                    order["id"] = i

            logging.info("Successfully generated and validated plan")
            return result

        except Exception as e:
            logging.error(f"Error in generate_strategy: {str(e)}", exc_info=True)
            console.print("[red]Error in generate_strategy:[/red]", style="bold red")
            console.print(f"[red]Error details: {str(e)}[/red]")
            raise Exception(f"Error generating strategy with Gemini: {str(e)}")

