from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import types

from company_data.llm.base import ILLMEnvironmentConfig, ILLMProvider, T


class GeminiProvider(ILLMProvider):
    def __init__(self, config: ILLMEnvironmentConfig) -> None:
        super().__init__(config)
        self.client = genai.Client()

    def generate_text(self, prompt: str, system_instructions: str | None = None):
        config = None
        if system_instructions is not None:
            config = types.GenerateContentConfig(system_instruction=system_instructions)

        response = self.client.models.generate_content(
            model=str(self.config.model_name),
            contents=prompt,
            config=config,
        )

        return response.text or ""

    def generate_structured_output(
        self,
        prompt: str,
        response_schema: type[T],
        system_instructions: str,
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system_instructions,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        response = self.client.models.generate_content(
            model=str(self.config.model_name),
            contents=prompt,
            config=config,
        )
        return response_schema.model_validate_json(response.text or "{}")

    def call_with_tools(
        self, prompt: str, tools: list[Callable[..., Any]], system_instruction: str
    ) -> Any:
        # Gemini does not support tool calls in the same way as Ollama.
        # This method is a placeholder to maintain interface compatibility.
        raise NotImplementedError(
            "Tool calls are not supported with the GeminiProvider."
        )
