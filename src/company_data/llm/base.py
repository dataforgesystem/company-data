from abc import ABC, abstractmethod
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ILLMProvider(ABC):
    """Vendor-agnostic chat contract backed by a LangChain chat model."""

    def __init__(self, chat_model: BaseChatModel):
        self.chat_model = chat_model

    @abstractmethod
    def generate_text(self, prompt: str, system_instructions: str | None = None):
        raise NotImplementedError

    @abstractmethod
    def generate_structured_output(
        self,
        prompt: str,
        response_schema: type[T],
        system_instructions: str,
    ) -> T:
        raise NotImplementedError

    @abstractmethod
    def call_with_tools(
        self,
        prompt: str,
        tools: list[BaseTool],
        system_instruction: str,
    ) -> Any:
        raise NotImplementedError


class IEmbedder(ABC):
    """Contract for text embedding providers (semantic search, RAG)."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text into a fixed-size vector."""
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into fixed-size vectors."""
        raise NotImplementedError
