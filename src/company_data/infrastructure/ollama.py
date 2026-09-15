from collections.abc import Callable
from typing import Any

from ollama import Client

from company_data.interfaces.ai_provider import ILLMProvider, T


class OllamaProvider(ILLMProvider):
    def __init__(self, model_name: str, host: str) -> None:
        self.client = Client(host=host)
        self.model_name = model_name

    def generate_text(self, prompt: str, system_instructions: str | None = None):
        pass

    def generate_structured_output(
        self, prompt: str, response_schema: type[T], system_instructions: str
    ):
        pass

    def call_with_tools(
        self, prompt: str, tools: list[Callable[..., Any]], system_instruction: str
    ) -> Any:
        formatted_tools: list[Callable] = []
        for tool in tools:
            pass

        response = self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "context": prompt}],
            tools=formatted_tools,
        )
        return response.get("message", {}).get("tool_calls", [])
