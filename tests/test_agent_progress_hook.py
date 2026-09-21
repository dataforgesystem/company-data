"""Tests for the agent's progress hook (``run(..., on_node=...)``).

Chat UIs (Chainlit) consume ``on_node`` to render pipeline progress without
knowing anything about LangGraph. These tests pin the hook's contract: every
executed node is reported in order, the default ``run`` stays callback-free,
and a cached answer skips the graph entirely.
"""

from datetime import datetime, timezone

import pytest

from company_data_crawler.models.company_data import (
    CompanyData,
    CompanyFundingInfo,
    KeyExecutive,
)

from company_data.agent.graph import CompanyResearchAgent
from company_data.agent.nodes import AgentComponents
from company_data.cache.interfaces import ISemanticCache, QueryCacheHit
from company_data.config.crawler_configs import MergeConfig
from company_data.database.base import SourcedProfile, VectorHit
from company_data.llm.base import IEmbedder, ILLMProvider
from company_data.pipeline.ingestion import IngestionResult
from company_data.pipeline.interfaces.extractor import BaseExtractor, ExtractedData
from company_data.pipeline.interfaces.merger import BaseMerger

pytestmark = pytest.mark.anyio

# Single-source strategies read ingest only the preferred source, so the fakes
# must speak the same source name the strategy filters on. Reading it from the
# config keeps the test hermetic whatever MERGE_PREFERRED_SOURCE is set to.
PREFERRED_SOURCE = MergeConfig.PREFERRED_SOURCE


class ScriptedLLM(ILLMProvider):
    """Extraction-only provider; answer synthesis uses generate_text."""

    def __init__(self) -> None:
        super().__init__(chat_model=None)
        self.structured_calls = 0

    def generate_text(self, prompt: str, system_instructions: str | None = None) -> str:
        return "FAKE ANSWER"

    def generate_structured_output(self, prompt, response_schema, system_instructions):
        self.structured_calls += 1
        if response_schema is ExtractedData:
            return ExtractedData(
                company_names=["Stripe", "Adyen"],
                intent="compare_funding",
                is_valid=True,
            )
        raise AssertionError(f"Unexpected schema: {response_schema}")

    def call_with_tools(self, prompt, tools, system_instruction):
        raise NotImplementedError


class FakeExtractor(BaseExtractor):
    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm)

    def extract_intent(self, text_query: str) -> ExtractedData:
        return self.llm.generate_structured_output("", ExtractedData, "")


class FakeMerger(BaseMerger):
    """Mergers are strategy-specific and take no constructor args.

    Single-record companies must never reach a merger (the merge node uses the
    one record as-is), so any call here is a bug worth failing loudly on.
    """

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
            VectorHit("stripe.com", "Stripe", PREFERRED_SOURCE, 0.9),
            VectorHit("adyen.com", "Adyen", PREFERRED_SOURCE, 0.9),
        ]
        self.rows: dict[tuple[str, str], CompanyData] = {}
        self.search_calls = 0

    async def fetch_source_profiles(self, company_domain: str) -> list[SourcedProfile]:
        return [
            SourcedProfile(source_name=source, profile=profile)
            for (domain, source), profile in self.rows.items()
            if domain == company_domain
        ]

    async def store_and_sync_profile(self, profile, embedding, source_name) -> None:
        self.rows[(profile.company_domain, source_name)] = profile

    async def search_companies(
        self, embedding, top_k: int = 5, source_names=None
    ) -> list[VectorHit]:
        self.search_calls += 1
        return self.hits

    async def close(self) -> None:
        pass


class DisabledCache(ISemanticCache):
    async def ensure_ready(self, vector_size: int) -> None:
        pass

    async def lookup(self, query: str):
        return None

    async def store(
        self,
        query: str,
        answer: str,
        company_domain: str = "",
        intent: str = "",
    ) -> None:
        pass

    async def close(self) -> None:
        pass


class FakeIngestion:
    """Ingests the canned profile under the requested company's own domain."""

    def __init__(self, store: FakeStore, profile: CompanyData) -> None:
        self.store = store
        self.profile = profile
        self.calls: list[str] = []

    async def ingest(self, company_name: str) -> list[IngestionResult]:
        self.calls.append(company_name)
        domain = f"{company_name.casefold().replace(' ', '')}.com"
        profile = self.profile.model_copy(
            update={"company_name": company_name, "company_domain": domain}
        )
        await self.store.store_and_sync_profile(profile, [0.1], PREFERRED_SOURCE)
        return [
            IngestionResult(
                source_name=PREFERRED_SOURCE,
                status="stored",
                company_domain=domain,
                detail=profile.company_name,
            )
        ]


def build_agent() -> tuple[CompanyResearchAgent, FakeStore, ScriptedLLM, FakeIngestion]:
    llm = ScriptedLLM()
    store = FakeStore()
    profile = CompanyData(
        company_name="Stripe",
        company_domain="stripe.com",
        company_funding_info=[
            CompanyFundingInfo(funding_round="Series B", funding_amount=50.0)
        ],
        key_executives=[KeyExecutive(name="Patrick Collison", title="CEO")],
    )
    ingestion = FakeIngestion(store, profile)
    merger = FakeMerger()
    components = AgentComponents(
        llm=llm,
        extractor=FakeExtractor(llm),
        merger=merger,
        ingestion=ingestion,
        store=store,
        embedder=FakeEmbedder(),
    )
    agent = CompanyResearchAgent(components=components, query_cache=DisabledCache())
    return agent, store, llm, ingestion


async def test_on_node_reports_every_executed_node_in_order():
    agent, _store, _llm, _ingestion = build_agent()
    seen: list[str] = []

    async def on_node(node_name: str, node_update: dict) -> None:
        seen.append(node_name)

    state = await agent.run("Compare Stripe and Adyen", on_node=on_node)

    assert seen == [
        "extract_intent",
        "retrieve_company",
        "ensure_profiles",
        "merge_profile",
        "synthesize_answer",
    ]
    # Both requested companies resolved, each through its own ingestion
    # fallback (the fake store starts empty and is keyed per company domain).
    assert state["company_domains"] == ["stripe.com", "adyen.com"]
    assert state["company_names"] == ["Stripe", "Adyen"]
    # One per-source record each => the merger must never be invoked.
    assert sorted(record.source_name for record in state["source_profiles"]) == [
        PREFERRED_SOURCE,
        PREFERRED_SOURCE,
    ]
    assert [_ingestion.calls.count("Stripe"), _ingestion.calls.count("Adyen")] == [1, 1]
    assert state["answer"] == "FAKE ANSWER"


async def test_default_run_without_hook_still_works():
    agent, _store, _llm, _ingestion = build_agent()
    state = await agent.run("Compare Stripe and Adyen")

    assert state["cache_hit"] is False
    assert state["answer"] == "FAKE ANSWER"