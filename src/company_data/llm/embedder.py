from collections.abc import Callable
from typing import Any

from ollama import Client

from company_data.llm.base import IEmbedder, ILLMEnvironmentConfig


class OllamaEmbedder(IEmbedder):
    """Embedding provider backed by an Ollama model (e.g. nomic-embed-text)."""

    def __init__(self, config: ILLMEnvironmentConfig) -> None:
        self.client = Client(host=config.host)
        self.model_name = config.model_name

    def embed(self, text: str) -> list[float]:
        response = self.client.embed(model=str(self.model_name), input=text)
        embeddings = response["embeddings"]
        if not embeddings:
            raise ValueError(f"Ollama returned no embedding for text: {text[:80]!r}")
        return embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embed(model=str(self.model_name), input=texts)
        return response["embeddings"]
