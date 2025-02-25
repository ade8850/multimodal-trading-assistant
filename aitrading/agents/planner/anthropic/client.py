import json
import os
from typing import Dict, List, Any
import traceback
from anthropic import Anthropic, AnthropicVertex
from ..base import BaseAIClient
from ....schema import SchemaConverter
import logfire


def create_anthropic_client(provider: str, api_key: str, **kwargs) -> 'AnthropicBaseClient':
    """Factory function to create appropriate Anthropic client."""
    if provider == "anthropic-vertex":
        return AnthropicVertexClient(api_key, **kwargs)
    return AnthropicAPIClient(api_key)


class AnthropicBaseClient(BaseAIClient):
    """Base class for Anthropic clients."""

    def generate_strategy(self, system_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        try:
            logfire.info("Starting plan generation with Claude")
            formatted_images = [self._format_image(img) for img in images]
            
            schema = self._get_schema()
            final_system_prompt = self._prepare_prompt(system_prompt, schema)
            
            message = self._generate_content(formatted_images, final_system_prompt)
            result = self._process_response(message.content[0].text)
            
            logfire.info("Successfully generated and validated plan", tags=["anthropic"])
            return result
            
        except Exception as e:
            logfire.exception("Error generating strategy with Claude",
                            error=str(e),
                            traceback=traceback.format_exc())
            raise

    def _get_schema(self) -> Dict[str, Any]:
        from ....models import PlanResponse
        #PlanResponse.model_rebuild()
        schema = PlanResponse.model_json_schema()
        try:
            return SchemaConverter.convert(schema, "anthropic")
        except Exception as e:
            logfire.error("Error converting schema", error=str(e))
            raise

    def _prepare_prompt(self, system_prompt: str, schema: Dict[str, Any]) -> str:
        schema_requirements = f"""
Your response must be a valid JSON object matching the following schema exactly:
{json.dumps(schema, indent=2)}
        """
        return f"{system_prompt}\n\n{schema_requirements}"

    def _process_response(self, response_text: str) -> Dict[str, Any]:
        try:
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)

            if "plan" not in result and isinstance(result, dict):
                result = {"plan": result}

            if not self._validate_response(result):
                raise ValueError("Response validation failed")

            orders = result["plan"].get("orders", [])
            for i, order in enumerate(orders, 1):
                if order.get("id") != i:
                    logfire.debug("Fixing order ID", old_id=order.get("id"), new_id=i)
                    order["id"] = i

            return result

        except json.JSONDecodeError as e:
            logfire.error("JSON parsing error",
                         error=str(e),
                         response_text=response_text)
            raise ValueError(f"Invalid JSON response from Claude: {str(e)}")

    def _format_image(self, image_bytes: bytes) -> Dict[str, Any]:
        import base64
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
        }

    def _generate_content(self, formatted_images: List[Dict], final_system_prompt: str) -> Any:
        raise NotImplementedError


class AnthropicAPIClient(AnthropicBaseClient):
    """Client for Anthropic's Claude model using direct API."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        logfire.info("Anthropic API client initialized")

    def _generate_content(self, formatted_images: List[Dict], final_system_prompt: str) -> Any:
        with logfire.span("generate_content"):
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                system=final_system_prompt,
                messages=[{
                    "role": "user",
                    "content": formatted_images
                }]
            )


class AnthropicVertexClient(AnthropicBaseClient):
    """Client for Anthropic's Claude model using Vertex AI."""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key)
        try:
            project_id = kwargs.get("vertex_project") or os.environ["VERTEX_PROJECT_ID"]
            region = kwargs.get("vertex_region") or os.environ["VERTEX_REGION"]
            
            self.client = AnthropicVertex(
                project_id=project_id,
                region=region
            )
            #self.model = "claude-3-5-sonnet-v2@20241022"
            self.model = "claude-3-7-sonnet@20250219"
            logfire.info("Anthropic Vertex client initialized",
                        project_id=project_id, 
                        region=region)
        except KeyError as e:
            raise ValueError(f"Missing required environment variable: {str(e)}")

    def _generate_content(self, formatted_images: List[Dict], final_system_prompt: str) -> Any:
        with logfire.span("generate_content"):
            return self.client.messages.create(
                model=self.model,
                max_tokens=20000,
                # thinking={
                #     "type": "enabled",
                #     "budget_tokens": 16000
                # },
                messages=[{
                    "role": "user",
                    "content": formatted_images + [{
                        "type": "text",
                        "text": final_system_prompt
                    }]
                }],
                system="You must respond only with a valid JSON object that matches the schema provided in the prompt. Do not include any other text before or after the JSON.",
                #max_tokens=4096,
                temperature=0
            )