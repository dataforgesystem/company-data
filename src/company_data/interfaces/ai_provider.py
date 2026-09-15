from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ILLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, system_instructions: str | None = None):
        pass

    @abstractmethod
    def generate_structured_output(
        self, prompt: str, response_schema: type[T], system_instructions: str
    ):
        pass

    @abstractmethod
    def call_with_tools(
        self, prompt: str, tools: list[Callable], system_instruction: str
    ) -> Any:
        pass
