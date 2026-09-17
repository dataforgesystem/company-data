"""Contracts for the semantic query cache."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryCacheHit:
    """One cached query/answer pair found by semantic lookup."""

    query: str
    answer: str
    company_domain: str
    intent: str
    created_at: float
    score: float


class IQueryCacheStore(ABC):
    """Vector-backed storage of query/answer pairs (one point per query)."""

    @abstractmethod
    async def ensure_collection(self, vector_size: int) -> None:
        """Creates the cache collection when it is missing."""

    @abstractmethod
    async def search(
        self, embedding: list[float], top_k: int = 1
    ) -> list[QueryCacheHit]:
        """Returns the closest cached queries to ``embedding``."""

    @abstractmethod
    async def upsert(
        self, point_id: str, embedding: list[float], payload: dict
    ) -> None:
        """Stores (or replaces) one cached query/answer point."""

    @abstractmethod
    async def close(self) -> None:
        """Releases any clients held by the store."""


class ISemanticCache(ABC):
    """Contract for the answer cache consulted before running the agent."""

    @abstractmethod
    async def ensure_ready(self, vector_size: int) -> None:
        """Prepares the backing store for reads and writes."""

    @abstractmethod
    async def lookup(self, query: str) -> QueryCacheHit | None:
        """Returns a trustworthy cached answer, or ``None`` on a miss."""

    @abstractmethod
    async def store(
        self, query: str, answer: str, company_domain: str = "", intent: str = ""
    ) -> None:
        """Caches the answer produced for ``query``."""

    @abstractmethod
    async def close(self) -> None:
        """Releases any clients held by the cache."""