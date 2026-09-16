from abc import ABC, abstractmethod
from typing import Any, TypeVar

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class ILLMEnvironmentConfig(BaseModel):
    API_KEY: str | None = Field(..., description="The API key for the LLM")
    model_name: str | None = Field(..., description="The name of the LLM model to use")
    host: str | None = Field(None, description="The host for the LLM (if applicable)")


class LLMProvider(ABC):

    def __init__(self, config: ILLMEnvironmentConfig):
        self.config = config

    @abstractmethod
    def generate_text(self, prompt: str, system_instructions: str | None = None):
        pass

    @abstractmethod
    def generate_structured_output(
        self,
        prompt: str,
        response_schema: type[T],
        system_instructions: str,
    ) -> T:
        pass

    @abstractmethod
    def call_with_tools(
        self, prompt: str, tools: list[BaseTool], system_instruction: str
    ) -> Any:
        pass
