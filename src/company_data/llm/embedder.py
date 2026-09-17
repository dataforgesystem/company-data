from langchain_core.embeddings import Embeddings

from company_data.llm.base import IEmbedder


class LangChainEmbedder(Embeddings, IEmbedder):
    """Embedder backed by any LangChain ``Embeddings`` implementation.

    Implements both interfaces: the project's ``IEmbedder`` (used by the
    ingestion pipeline) and LangChain's ``Embeddings`` (so it can be handed
    straight to LangChain vector stores or retrievers).
    """

    def __init__(self, embeddings: Embeddings) -> None:
        self.embeddings = embeddings

    def embed(self, text: str) -> list[float]:
        return list(self.embeddings.embed_query(text))

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [list(vector) for vector in self.embeddings.embed_documents(texts)]

    # LangChain Embeddings interface (delegating).
    def embed_query(self, text: str) -> list[float]:
        return self.embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_batch(texts)
