from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar, Optional

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class ILLMEnvironmentConfig(BaseModel):
    API_KEY: Optional[str] = Field(..., description="The API key for the LLM")
    model_name: Optional[str] = Field(
        ..., description="The name of the LLM model to use"
    )
    host: Optional[str] = Field(
        None, description="The host for the LLM (if applicable)"
    )


class ILLMProvider(ABC):

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
        self, prompt: str, tools: list[Callable], system_instruction: str
    ) -> Any:
        pass
