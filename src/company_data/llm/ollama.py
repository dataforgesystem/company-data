from collections.abc import Callable
from typing import Any

from ollama import Client

from company_data.llm.base import ILLMEnvironmentConfig, ILLMProvider, T


class OllamaProvider(ILLMProvider):
    def __init__(self, config: ILLMEnvironmentConfig) -> None:
        self.client = Client(host=config.host)
        self.model_name = config.model_name

    def generate_text(self, prompt: str, system_instructions: str | None = None):
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        if system_instructions is not None:
            messages.insert(0, {"role": "system", "content": system_instructions})
        response = self.client.chat(
            model=self.model_name,
            messages=messages,
        )
        return response.get("message", {}).get("content", "")

    def generate_structured_output(
        self,
        prompt: str,
        response_schema: type[T],
        system_instructions: str,
    ) -> T:
        response = self.client.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": prompt},
            ],
            format=response_schema.model_json_schema(),
            options={"temperature": 0.0},
        )
        content = response.get("message", {}).get("content", "")
        return response_schema.model_validate_json(content)

    def call_with_tools(
        self, prompt: str, tools: list[Callable[..., Any]], system_instruction: str
    ) -> Any:
        formatted_tools: list[Callable] = []
        for tool in tools:
            pass

        response = self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            tools=formatted_tools,
        )
        return response.get("message", {}).get("tool_calls", [])
