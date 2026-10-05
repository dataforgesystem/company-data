"""Tests for the semantic query cache.

The cache decides whether a previous answer can stand in for a new question, so
these tests pin down the decision boundary (threshold, TTL, empty queries) and
the robustness rule that a broken cache degrades to a miss, never an error.
"""

import math
import time

import pytest

from company_data.cache.interfaces import IQueryCacheStore, QueryCacheHit
from company_data.cache.semantic_cache import SemanticQueryCache
from company_data.llm.base import IEmbedder

pytestmark = pytest.mark.anyio

# Known phrases mapped onto a unit circle, so cosine similarity is controllable.
VOCAB = {"tesla competitors": 0.0, "who competes with tesla": 0.05, "tesla funding": 1.0}


class FakeEmbedder(IEmbedder):
    """Deterministic embeddings for the phrases the tests use.

    Normalizes whitespace/case like the real embedder treats text, so a
    reworded-but-equivalent query lands on the same vector.
    """

    def embed(self, text: str) -> list[float]:
        angle = VOCAB.get(" ".join(text.split()).lower(), 2.0)
        return [math.cos(angle), math.sin(angle)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


def cosine(left, right) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    return dot / (math.hypot(*left) * math.hypot(*right))


class FakeQueryCacheStore(IQueryCacheStore):
    """In-memory stand-in for Qdrant, using real vector similarity."""

    def __init__(self) -> None:
        self.points: dict[str, tuple[list[float], dict]] = {}
        self.search_calls = 0
        self.fail = False

    async def ensure_collection(self, vector_size: int) -> None:
        if self.fail:
            raise RuntimeError("store down")

    async def search(
        self, embedding, top_k: int = 1, scope: str = ""
    ) -> list[QueryCacheHit]:
        self.search_calls += 1
        self.last_scope = scope
        if self.fail:
            raise RuntimeError("store down")
        # Exact-match scope filter, like the real Qdrant store: entries from
        # another conversation's scope (including ones with no scope at all)
        # are never candidates.
        scored = [
            (
                cosine(embedding, vector),
                QueryCacheHit(
                    query=payload["query"],
                    answer=payload["answer"],
                    company_domain=payload.get("company_domain", ""),
                    intent=payload.get("intent", ""),
                    created_at=payload["created_at"],
                    score=0.0,
                    company_names=tuple(payload.get("company_names") or ()),
                    scope=str(payload.get("scope", "")),
                ),
            )
            for vector, payload in self.points.values()
            if str(payload.get("scope", "")) == scope
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            QueryCacheHit(
                query=hit.query,
                answer=hit.answer,
                company_domain=hit.company_domain,
                intent=hit.intent,
                created_at=hit.created_at,
                score=score,
                company_names=hit.company_names,
                scope=hit.scope,
            )
            for score, hit in scored[:top_k]
        ]

    async def upsert(self, point_id, embedding, payload) -> None:
        if self.fail:
            raise RuntimeError("store down")
        self.points[point_id] = (embedding, payload)

    async def close(self) -> None:
        pass


def make_cache(store, threshold=0.99, ttl_seconds=3600, enabled=True):
    return SemanticQueryCache(
        embedder=FakeEmbedder(),
        store=store,
        threshold=threshold,
        ttl_seconds=ttl_seconds,
        enabled=enabled,
    )


async def test_stored_answer_is_returned_for_the_same_query():
    store = FakeQueryCacheStore()
    cache = make_cache(store)

    await cache.store("tesla competitors", "Rivian, Lucid", "tesla.com", "competitors")
    hit = await cache.lookup("tesla competitors")

    assert hit is not None
    assert hit.answer == "Rivian, Lucid"
    assert hit.company_domain == "tesla.com"
    assert hit.score == pytest.approx(1.0)


async def test_near_identical_wording_hits():
    """The point of a semantic cache: a reworded repeat is still a hit."""
    store = FakeQueryCacheStore()
    cache = make_cache(store, threshold=0.99)

    await cache.store("tesla competitors", "Rivian, Lucid")
    hit = await cache.lookup("who competes with tesla")

    assert hit is not None
    assert hit.answer == "Rivian, Lucid"


async def test_distant_query_misses():
    """A different information need must not reuse an unrelated answer."""
    store = FakeQueryCacheStore()
    cache = make_cache(store, threshold=0.99)

    await cache.store("tesla competitors", "Rivian, Lucid")

    assert await cache.lookup("tesla funding") is None


async def test_threshold_controls_how_eagerly_it_hits():
    """The same near-miss becomes a hit once the threshold is relaxed."""
    store = FakeQueryCacheStore()
    await make_cache(store, threshold=0.99).store("tesla competitors", "Rivian, Lucid")

    strict = await make_cache(store, threshold=0.9999).lookup("who competes with tesla")
    loose = await make_cache(store, threshold=0.9).lookup("who competes with tesla")

    assert strict is None
    assert loose is not None


async def test_stale_entries_expire():
    store = FakeQueryCacheStore()
    cache = make_cache(store, ttl_seconds=1)
    await cache.store("tesla competitors", "Rivian, Lucid")
    store.points = {
        key: (vector, {**payload, "created_at": time.time() - 10})
        for key, (vector, payload) in store.points.items()
    }

    assert await cache.lookup("tesla competitors") is None


async def test_empty_query_is_never_looked_up():
    store = FakeQueryCacheStore()

    assert await make_cache(store).lookup("   ") is None
    assert store.search_calls == 0


async def test_disabled_cache_touches_nothing():
    store = FakeQueryCacheStore()
    cache = make_cache(store, enabled=False)

    await cache.store("tesla competitors", "Rivian, Lucid")
    await cache.ensure_ready(2)

    assert await cache.lookup("tesla competitors") is None
    assert store.points == {}


async def test_broken_store_degrades_to_a_miss():
    """A cache outage must never fail the query it is meant to speed up."""
    store = FakeQueryCacheStore()
    store.fail = True
    cache = make_cache(store)

    await cache.ensure_ready(2)
    await cache.store("tesla competitors", "Rivian, Lucid")

    assert await cache.lookup("tesla competitors") is None


async def test_empty_answers_are_not_cached():
    store = FakeQueryCacheStore()

    await make_cache(store).store("tesla competitors", "")

    assert store.points == {}


async def test_restoring_the_same_query_replaces_its_entry():
    """Re-answering a question updates one point instead of piling up."""
    store = FakeQueryCacheStore()
    cache = make_cache(store)

    await cache.store("tesla competitors", "old answer")
    await cache.store("  Tesla   Competitors ", "new answer")

    hit = await cache.lookup("tesla competitors")
    assert hit is not None
    assert hit.answer == "new answer"


# ------------------------------------------------------- conversation scoping


async def test_followup_answer_is_scoped_to_its_companies():
    """The same follow-up text in different conversations is different data.

    "and their employees?" is byte-identical in a conversation about Tesla and
    one about Adyen while expecting different answers, so similarity alone can
    never be trusted: the scope must match exactly.
    """
    store = FakeQueryCacheStore()
    cache = make_cache(store, threshold=0.5)
    await cache.store(
        "and their employees?",
        "Tesla has about 140k employees",
        company_names=["Tesla"],
        scope="tesla",
    )

    hit = await cache.lookup("and their employees?", scope="tesla")
    assert hit is not None
    assert hit.answer == "Tesla has about 140k employees"
    assert hit.company_names == ("Tesla",)
    assert hit.scope == "tesla"

    # A different company's conversation gets a miss, not Tesla's answer.
    assert await cache.lookup("and their employees?", scope="adyen") is None


async def test_scoped_and_unscoped_entries_coexist():
    store = FakeQueryCacheStore()
    cache = make_cache(store, threshold=0.5)
    await cache.store("tesla competitors", "Rivian, Lucid")  # no conversation
    await cache.store(
        "tesla competitors", "same but scoped", company_names=["Tesla"], scope="tesla"
    )

    unscoped = await cache.lookup("tesla competitors")
    scoped = await cache.lookup("tesla competitors", scope="tesla")
    assert unscoped is not None and unscoped.answer == "Rivian, Lucid"
    assert scoped is not None and scoped.answer == "same but scoped"
    assert len(store.points) == 2


async def test_scope_is_recorded_with_the_entry_for_memory():
    store = FakeQueryCacheStore()
    cache = make_cache(store, threshold=0.5)
    await cache.store(
        "q",
        "a",
        company_domain="stripe.com",
        intent="funding",
        company_names=["Stripe", "Adyen"],
        scope="stripe|adyen",
    )

    hit = await cache.lookup("q", scope="stripe|adyen")
    assert hit is not None
    assert hit.company_names == ("Stripe", "Adyen")
    assert hit.company_domain == "stripe.com"

    assert len(store.points) == 1