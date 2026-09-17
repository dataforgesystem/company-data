"""Semantic cache for whole agent answers."""

import asyncio
import time
import uuid

from company_data.cache.interfaces import (
    IQueryCacheStore,
    ISemanticCache,
    QueryCacheHit,
)
from company_data.llm.base import IEmbedder
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class SemanticQueryCache(ISemanticCache):
    """Caches the answer to a query, matched by embedding similarity.

    A hit skips the entire graph - intent extraction, crawling, storing and
    merging - which is what makes a repeated question free instead of a fresh
    round of model and rate-limit spend.

    Two properties keep this safe to enable:

    - ``threshold`` is deliberately conservative. A semantic hit returns a
      previously generated answer without consulting a model, so unlike the
      exact-match response cache it *can* be wrong: "competitors of Tesla" and
      "customers of Tesla" are nearly identical sentences with unrelated
      answers. Raising the threshold towards ``1.0`` narrows matching to
      repeats and trivial rewordings.
    - the cache can never break a run. Every store interaction is best-effort:
      an unreachable or missing store is treated as a miss, never an error.
    """

    def __init__(
        self,
        embedder: IEmbedder,
        store: IQueryCacheStore,
        threshold: float = 0.97,
        ttl_seconds: int = 24 * 60 * 60,
        enabled: bool = True,
    ) -> None:
        self.embedder = embedder
        # Not named `store`: that would shadow this class's `store()` method.
        self.cache_store = store
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

    async def ensure_ready(self, vector_size: int) -> None:
        """Creates the cache collection, tolerating an unavailable store."""
        if not self.enabled:
            return
        try:
            await self.cache_store.ensure_collection(vector_size)
        except Exception as failure:
            logger.warning(f"Query cache unavailable, continuing without it: {failure!r}")

    async def lookup(self, query: str) -> QueryCacheHit | None:
        """Returns a cached answer when a close enough entry is trustworthy."""
        if not self.enabled or not query.strip():
            return None
        try:
            embedding = await asyncio.to_thread(self.embedder.embed, query)
            hits = await self.cache_store.search(embedding, top_k=1)
        except Exception as failure:
            logger.warning(f"Query cache lookup failed, treating as a miss: {failure!r}")
            return None

        hit = hits[0] if hits else None
        if hit is None or hit.score < self.threshold:
            best = f"{hit.score:.3f}" if hit else "none"
            logger.info(
                f"Query cache miss (best similarity {best} < {self.threshold})."
            )
            return None
        if time.time() - hit.created_at > self.ttl_seconds:
            logger.info("Query cache entry is older than its TTL; treating as a miss.")
            return None

        logger.info(f"Query cache hit (similarity {hit.score:.3f}) for {query!r}.")
        return hit

    async def store(
        self, query: str, answer: str, company_domain: str = "", intent: str = ""
    ) -> None:
        """Caches one answer; never raises, so a failure cannot fail the run."""
        if not self.enabled or not answer or not query.strip():
            return
        try:
            embedding = await asyncio.to_thread(self.embedder.embed, query)
            # Keyed by normalized query text, so re-answering the same question
            # replaces its entry instead of accumulating duplicate points.
            point_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, " ".join(query.split()).lower())
            )
            await self.cache_store.upsert(
                point_id,
                embedding,
                {
                    "query": query,
                    "answer": answer,
                    "company_domain": company_domain,
                    "intent": intent,
                    "created_at": time.time(),
                },
            )
            logger.info(f"Cached answer for {query!r}.")
        except Exception as failure:
            logger.warning(f"Query cache write failed, continuing: {failure!r}")

    async def close(self) -> None:
        """Releases the backing store, tolerating an already-broken client."""
        try:
            await self.cache_store.close()
        except Exception as failure:
            logger.warning(f"Query cache shutdown failed: {failure!r}")