import json
import logging
from typing import Dict, List, Any

import logfire
from anthropic import Anthropic
from ..base import BaseAIClient
from ....schema import SchemaConverter
from rich.console import Console

console = Console()

class AnthropicClient(BaseAIClient):
    """Client for interacting with Anthropic's Claude model."""

    def __init__(self, api_key: str):
        """Initialize the Anthropic client."""
        super().__init__(api_key)
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        #self.model = "claude-3-haiku-20240307"
        logfire.instrument_anthropic(self.client)
        logging.info("Anthropic client initialized")

    def generate_strategy(self, system_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using Claude."""
        try:
            console.print()
            console.print("Starting plan generation with Claude", style="bold green")

            # Process images
            formatted_images = self._format_images(images)

            # Generate schema
            from ....models import PlanResponse
            schema = PlanResponse.model_json_schema()

            # Convert schema for Claude
            try:
                claude_schema = SchemaConverter.convert(schema, "anthropic")
            except Exception as e:
                logging.error(f"Error converting schema: {str(e)}")
                raise

            # Add schema requirements to the system prompt
            schema_requirements = f"""
Your response must be a valid JSON object matching the following schema exactly:
{json.dumps(claude_schema, indent=2)}
            """

            final_system_prompt = f"{system_prompt}\n\n{schema_requirements}"

            # Generate content
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0,
                system=final_system_prompt,
                messages=[{
                    "role": "user",
                    "content": formatted_images
                }]
            )

            console.print()
            console.print("Raw response text: ", message.content[0].text, style="grey37")

            try:
                response_text = message.content[0].text.replace('\n', ' ').replace('    ', ' ')
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logging.error(f"JSON parsing error: {str(e)}")
                logging.error(f"Failed to parse response text: {message.content[0].text}")
                raise ValueError(f"Invalid JSON response from Claude: {str(e)}")

            # Ensure IDs match
            if not self._validate_response(result):
                raise ValueError("Response validation failed")

            # Ensure order IDs are progressive
            orders = result["plan"].get("orders", [])
            for i, order in enumerate(orders, 1):
                if order.get("id") != i:
                    console.print(f"[yellow]Fixing order ID from {order.get('id')} to {i}[/yellow]")
                    order["id"] = i

            return result

        except Exception as e:
            logging.error(f"Error in generate_strategy: {str(e)}", exc_info=True)
            console.print("[red]Error in generate_strategy:[/red]", style="bold red")
            console.print(f"[red]Error details: {str(e)}[/red]")
            raise Exception(f"Error generating strategy with Claude: {str(e)}")

    def _format_images(self, images: List[bytes]) -> List[Dict]:
        """Convert images to Claude's expected format."""
        return [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": self._encode_image(img)
            }
        } for img in images]

    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 string."""
        import base64
        return base64.b64encode(image_bytes).decode('utf-8')