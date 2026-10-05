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
    # Companies the answer was about. Needed so a turn served from the cache can
    # still seed conversation memory (a follow-up after a cache hit must be able
    # to name the company that was under discussion).
    company_names: tuple[str, ...] = ()
    # Conversation scope the entry was written in; see ISemanticCache.lookup.
    scope: str = ""


class IQueryCacheStore(ABC):
    """Vector-backed storage of query/answer pairs (one point per query)."""

    @abstractmethod
    async def ensure_collection(self, vector_size: int) -> None:
        """Creates the cache collection when it is missing."""

    @abstractmethod
    async def search(
        self, embedding: list[float], top_k: int = 1, scope: str = ""
    ) -> list[QueryCacheHit]:
        """Returns the closest cached queries recorded in ``scope``.

        ``scope`` is an exact-match filter, not a similarity: entries from a
        different conversation about a different company must never be
        candidates, however similar their text is.
        """

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
    async def lookup(self, query: str, scope: str = "") -> QueryCacheHit | None:
        """Returns a trustworthy cached answer, or ``None`` on a miss.

        ``scope`` identifies the companies the current conversation could be
        referring to (see ``ConversationMemory.cache_scope``). It matters
        because the cache matches on *question text*, and a follow-up like
        "and their employees?" is the identical text in a conversation about
        Stripe and one about Adyen while expecting different answers — the
        similarity would be 1.0, so without the scope the second conversation
        would silently receive the first one's answer.
        """

    @abstractmethod
    async def store(
        self,
        query: str,
        answer: str,
        company_domain: str = "",
        intent: str = "",
        company_names: list[str] | None = None,
        scope: str = "",
    ) -> None:
        """Caches the answer produced for ``query``.

        ``company_names`` and ``scope`` are stored with the entry so a later
        cache hit can still tell conversation memory which companies the answer
        was about and which conversation it belongs to.
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases any clients held by the cache."""