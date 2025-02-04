import json
import os
from typing import Dict, List, Any
import traceback
from anthropic import AnthropicVertex
from ..base import BaseAIClient
from ....schema import SchemaConverter
import logfire


class AnthropicClient(BaseAIClient):
    """Client for interacting with Anthropic's Claude model via Vertex."""

    def __init__(self, api_key: str):
        """Initialize the Anthropic client."""
        super().__init__(api_key)
        try:
            project_id = os.environ["VERTEX_PROJECT_ID"]
            region = os.environ["VERTEX_REGION"]
            
            self.client = AnthropicVertex(
                project_id=project_id,
                region=region
            )
            self.model = "claude-3-5-sonnet-v2@20241022"
            logfire.info("Anthropic client initialized", project_id=project_id, region=region)
        except KeyError as e:
            raise ValueError(f"Missing required environment variable: {str(e)}")
        except Exception as e:
            logfire.exception("Failed to initialize Anthropic client",
                          error=str(e))
            raise

    def generate_strategy(self, system_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using Claude.

        Args:
            system_prompt: Framework and rules for analysis
            images: List of chart images in PNG format

        Returns:
            Complete plan with analysis and orders
        """
        try:
            logfire.info("Starting plan generation with Claude")

            # Process images for Claude format
            formatted_images = [self._format_image(img) for img in images]

            # Generate schema
            from ....models import PlanResponse
            schema = PlanResponse.model_json_schema()

            # Convert schema for Claude
            try:
                claude_schema = SchemaConverter.convert(schema, "anthropic")
            except Exception as e:
                logfire.error("Error converting schema",
                            error=str(e),
                            traceback=traceback.format_exc())
                raise

            # Add schema requirements to system prompt
            schema_requirements = f"""
Your response must be a valid JSON object matching the following schema exactly:
{json.dumps(claude_schema, indent=2)}
            """

            final_system_prompt = f"{system_prompt}\n\n{schema_requirements}"

            # Generate content
            with logfire.span("generate_content"):
                message = self.client.messages.create(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": formatted_images + [{
                            "type": "text",
                            "text": final_system_prompt
                        }]
                    }],
                    system="You must respond only with a valid JSON object that matches the schema provided in the prompt. Do not include any other text before or after the JSON.",
                    max_tokens=4096,
                    temperature=0
                )

                response_text = message.content[0].text
                logfire.debug("Raw response text", text=response_text)

                try:
                    # Remove any non-JSON text and extract JSON object
                    response_text = response_text.strip()
                    if response_text.startswith('```json'):
                        response_text = response_text[7:]
                    if response_text.endswith('```'):
                        response_text = response_text[:-3]
                    response_text = response_text.strip()
                    
                    result = json.loads(response_text)

                    # Ensure result is wrapped in expected structure
                    if "plan" not in result and isinstance(result, dict):
                        result = {"plan": result}

                except json.JSONDecodeError as e:
                    logfire.error("JSON parsing error",
                                error=str(e),
                                response_text=response_text,
                                traceback=traceback.format_exc())
                    raise ValueError(f"Invalid JSON response from Claude: {str(e)}")

                # Validate response structure and content
                if not self._validate_response(result):
                    raise ValueError("Response validation failed")

                # Ensure order IDs are progressive
                orders = result["plan"].get("orders", [])
                for i, order in enumerate(orders, 1):
                    if order.get("id") != i:
                        logfire.debug("Fixing order ID", old_id=order.get("id"), new_id=i)
                        order["id"] = i

                logfire.info("Successfully generated and validated plan", tags=["anthropic"])
                return result

        except Exception as e:
            logfire.exception("Error generating strategy with Claude",
                            error=str(e),
                            traceback=traceback.format_exc())
            raise

    def _format_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """Format image for Claude message API."""
        import base64
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
        }