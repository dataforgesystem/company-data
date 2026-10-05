"""Agent-level tests for conversation context.

Pins how ``CompanyResearchAgent.run`` consumes a :class:`ConversationMemory`:
the history reaches the extractor, the answer cache is scoped to the companies
under discussion, and a turn served from the cache still seeds the memory so a
follow-up after a cache hit resolves. No LLM, database, or Qdrant is needed.
"""

import pytest

from company_data.agent.conversation import ConversationMemory
from company_data.agent.graph import CompanyResearchAgent
from company_data.agent.nodes import AgentComponents
from company_data.cache.interfaces import ISemanticCache, QueryCacheHit
from company_data.config.crawler_configs import MergeConfig
from company_data.database.base import SourcedProfile, VectorHit
from company_data.llm.base import IEmbedder, ILLMProvider
from company_data.pipeline.ingestion import IngestionResult
from company_data.pipeline.interfaces.extractor import BaseExtractor, ExtractedData
from company_data.pipeline.interfaces.merger import BaseMerger
from company_data_crawler.models.company_data import CompanyData

pytestmark = pytest.mark.anyio

PREFERRED = MergeConfig.PREFERRED_SOURCE


class ScriptedLLM(ILLMProvider):
    """Extraction-only provider that records the system prompt it was given."""

    def __init__(self) -> None:
        super().__init__(chat_model=None)
        self.contexts: list[str] = []

    def generate_text(self, prompt: str, system_instructions: str | None = None) -> str:
        return "FAKE ANSWER"

    def generate_structured_output(self, prompt, response_schema, system_instructions):
        self.contexts.append(system_instructions)
        return ExtractedData(
            company_names=["Stripe", "Adyen"],
            intent="compare_funding",
            is_valid=True,
        )

    def call_with_tools(self, prompt, tools, system_instruction):
        raise NotImplementedError


class FakeExtractor(BaseExtractor):
    """Records the conversation context the node handed it."""

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm)
        self.contexts: list[str | None] = []

    def extract_intent(
        self, text_query: str, conversation_context: str | None = None
    ) -> ExtractedData:
        self.contexts.append(conversation_context)
        return self.llm.generate_structured_output("", ExtractedData, "")


class FakeMerger(BaseMerger):
    def merge_profiles(self, records, focus_query=None) -> CompanyData:
        raise AssertionError("single-record companies must not merge")


class FakeEmbedder(IEmbedder):
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeStore:
    def __init__(self) -> None:
        self.hits = [
            VectorHit("stripe.com", "Stripe", PREFERRED, 0.9),
            VectorHit("adyen.com", "Adyen", PREFERRED, 0.9),
        ]
        self.rows: dict[tuple[str, str], CompanyData] = {}

    async def fetch_source_profiles(self, company_domain: str) -> list[SourcedProfile]:
        return [
            SourcedProfile(source_name=source, profile=profile)
            for (domain, source), profile in self.rows.items()
            if domain == company_domain
        ]

    async def store_and_sync_profile(self, profile, embedding, source_name) -> None:
        self.rows[(profile.company_domain, source_name)] = profile

    async def search_companies(self, embedding, top_k=5, source_names=None):
        return self.hits

    async def close(self) -> None:
        pass


class FakeIngestion:
    async def ingest(self, company_name: str) -> list[IngestionResult]:
        domain = f"{company_name.casefold().replace(' ', '')}.com"
        profile = CompanyData(company_name=company_name, company_domain=domain)
        await self.store.store_and_sync_profile(profile, [0.1], PREFERRED)
        return [
            IngestionResult(
                source_name=PREFERRED,
                status="stored",
                company_domain=domain,
                detail=company_name,
            )
        ]
class FakeIngestionWithStore(FakeIngestion):
    """Binds a store so ingestion can write into it."""

    def __init__(self, store: FakeStore) -> None:
        self.store = store


class RecordingCache(ISemanticCache):
    """Never hits; records the scope of every lookup and store."""

    def __init__(self) -> None:
        self.looked_up_scopes: list[str] = []
        self.stored: list[dict] = []

    async def ensure_ready(self, vector_size: int) -> None:
        pass

    async def lookup(self, query: str, scope: str = ""):
        self.looked_up_scopes.append(scope)
        return None

    async def store(
        self,
        query: str,
        answer: str,
        company_domain: str = "",
        intent: str = "",
        company_names: list[str] | None = None,
        scope: str = "",
    ) -> None:
        self.stored.append(
            {
                "query": query,
                "company_names": list(company_names or []),
                "scope": scope,
            }
        )

    async def close(self) -> None:
        pass


def build_agent(llm: ScriptedLLM, cache: ISemanticCache) -> CompanyResearchAgent:
    store = FakeStore()
    return CompanyResearchAgent(
        components=AgentComponents(
            llm=llm,
            extractor=FakeExtractor(llm),
            merger=FakeMerger(),
            ingestion=FakeIngestionWithStore(store),
            store=store,
            embedder=FakeEmbedder(),
        ),
        query_cache=cache,
    )
async def test_first_turn_sends_no_context_and_empty_scope():
    llm = ScriptedLLM()
    cache = RecordingCache()
    agent = build_agent(llm, cache)
    extractor = agent.components.extractor

    await agent.run("Compare Stripe and Adyen")

    # First turn: the extractor is told the query stands alone.
    assert extractor.contexts == [None]
    assert cache.looked_up_scopes == [""]
    # The answer was cached with its companies and the empty scope.
    assert cache.stored[0]["company_names"] == ["Stripe", "Adyen"]
    assert cache.stored[0]["scope"] == ""


async def test_followup_receives_history_and_scoped_cache():
    llm = ScriptedLLM()
    cache = RecordingCache()
    agent = build_agent(llm, cache)
    extractor = agent.components.extractor

    await agent.run("Compare Stripe and Adyen")
    await agent.run("and their employees?")

    assert extractor.contexts[0] is None
    assert extractor.contexts[1] is not None
    assert "Compare Stripe and Adyen" in extractor.contexts[1]
    assert "and their employees?" not in extractor.contexts[1]  # current turn excluded
    # The scope names the companies under discussion, so the follow-up can
    # never be answered from another conversation's cache entry.
    assert cache.looked_up_scopes[1] == "stripe|adyen"
    assert cache.stored[1]["scope"] == "stripe|adyen"


async def test_conversation_can_be_injected_per_call():
    llm = ScriptedLLM()
    cache = RecordingCache()
    agent = build_agent(llm, cache)
    extractor = agent.components.extractor
    own_memory = ConversationMemory(history_turns=4, enabled=True)
    own_memory.record(
        {
            "query": "Tell me about Stripe",
            "answer": "It is a payments company.",
            "company_names": ["Stripe"],
        }
    )

    await agent.run("and their funding?", conversation=own_memory)

    assert extractor.contexts[0] is not None
    assert "Tell me about Stripe" in extractor.contexts[0]
    assert cache.looked_up_scopes[0] == "stripe"

async def test_cached_hit_still_seeds_memory_for_the_next_followup():
    """A follow-up after a cache hit must name the cached company.

    A cache hit returns no ``extracted``; memory falls back to the
    ``company_names`` the cache entry carries.
    """

    class HitOnceCache(RecordingCache):
        def __init__(self) -> None:
            super().__init__()
            self.answered = False

        async def lookup(self, query: str, scope: str = ""):
            self.looked_up_scopes.append(scope)
            if self.answered:
                return QueryCacheHit(
                    query=query,
                    answer="CACHED ANSWER",
                    company_domain="stripe.com",
                    intent="funding",
                    created_at=0.0,
                    score=0.99,
                    company_names=("Stripe",),
                    scope=scope,
                )
            return None

        async def store(
            self,
            query: str,
            answer: str,
            company_domain: str = "",
            intent: str = "",
            company_names: list[str] | None = None,
            scope: str = "",
        ) -> None:
            self.answered = True  # first run caches; later runs hit

    llm = ScriptedLLM()
    cache = HitOnceCache()
    agent = build_agent(llm, cache)

    first = await agent.run("Compare Stripe and Adyen")
    assert first["cache_hit"] is False

    second = await agent.run("and their employees?")
    assert second["cache_hit"] is True
    assert second["answer"] == "CACHED ANSWER"

    # The cached turn recorded the company names, so the scope is populated.
    assert cache.looked_up_scopes[-1] == "stripe|adyen"


async def test_memory_is_bounded_across_many_turns():
    llm = ScriptedLLM()
    agent = build_agent(llm, RecordingCache())

    for index in range(10):
        await agent.run(f"question {index} about Stripe and Adyen")

    assert len(agent.conversation) <= agent.conversation.history_turns

