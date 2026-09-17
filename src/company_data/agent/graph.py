"""Wires the company research agent graph (extract -> retrieve -> ingest on
miss -> merge on demand -> synthesize) and exposes a runnable agent."""

import asyncio

from langgraph.graph import END, START, StateGraph

from company_data.agent import edges, nodes
from company_data.agent.nodes import AgentComponents
from company_data.agent.state import AgentState
from company_data.cache.interfaces import ISemanticCache
from company_data.cache.semantic_cache import SemanticQueryCache
from company_data.config.cache_configs import CacheConfig
from company_data.config.db_configs import DBConfig
from company_data.config.llm_configs import LLMConfig
from company_data.database.company_store_orchestrator import CompanyStoreOrchestrator
from company_data.database.relational.postgres import PostgresStore
from company_data.database.vector.qdrant import QdrantStore
from company_data.database.vector.query_cache import QdrantQueryCacheStore
from company_data.llm.base import IEmbedder
from company_data.llm.embedder import LangChainEmbedder
from company_data.llm.llm_client import LLMProvider
from company_data.llm.response_cache import configure_llm_cache
from company_data.pipeline.ingestion import IngestionPipeline
from company_data.pipeline.llm_extractor import LLMExtractor
from company_data.pipeline.llm_merger import LLMProfileMerger
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


def build_graph(components: AgentComponents):
    """Compiles the research graph from the given components."""
    builder = StateGraph(AgentState)
    builder.add_node("extract_intent", nodes.extract_intent_node(components))
    builder.add_node("retrieve_company", nodes.retrieve_company_node(components))
    builder.add_node("ensure_profiles", nodes.ensure_profiles_node(components))
    builder.add_node("merge_profile", nodes.merge_profile_node(components))
    builder.add_node("synthesize_answer", nodes.synthesize_answer_node(components))
    builder.add_node("respond_invalid_intent", nodes.respond_invalid_intent_node(components))

    builder.add_edge(START, "extract_intent")
    builder.add_conditional_edges(
        "extract_intent",
        edges.route_after_intent,
        {
            "retrieve_company": "retrieve_company",
            "respond_invalid_intent": "respond_invalid_intent",
        },
    )
    builder.add_edge("retrieve_company", "ensure_profiles")
    builder.add_edge("ensure_profiles", "merge_profile")
    builder.add_edge("merge_profile", "synthesize_answer")
    builder.add_edge("synthesize_answer", END)
    builder.add_edge("respond_invalid_intent", END)
    return builder.compile()


def build_default_components() -> AgentComponents:
    """Wires every component from project configs (the composition root).

    Each LLM consumer gets its own model, so a cheap local model can handle
    cheap steps while a stronger hosted model handles reconciliation:

    - intent extraction  -> :attr:`LLMConfig.QUERY_INTENT_EXTRACTION_MODEL`
    - profile merging    -> :attr:`LLMConfig.PROFILE_MERGE_MODEL`
    - answer synthesis   -> :attr:`LLMConfig.ANSWER_MODEL`

    Also installs the shared exact-match response cache, so repeated identical
    prompts (across runs, not just within one) never re-hit a provider.
    """
    configure_llm_cache()
    embedder = LangChainEmbedder(LLMConfig.embedding_model())
    store = CompanyStoreOrchestrator(
        PostgresStore(DBConfig.PG_CONNECTION_STRING),
        QdrantStore(DBConfig.QDRANT_URL, DBConfig.QDRANT_COLLECTION),
    )
    return AgentComponents(
        llm=LLMProvider(LLMConfig.chat_model(LLMConfig.ANSWER_MODEL)),
        extractor=LLMExtractor(
            LLMProvider(LLMConfig.chat_model(LLMConfig.QUERY_INTENT_EXTRACTION_MODEL))
        ),
        merger=LLMProfileMerger(
            LLMProvider(LLMConfig.chat_model(LLMConfig.PROFILE_MERGE_MODEL))
        ),
        ingestion=IngestionPipeline(store, embedder),
        store=store,
        embedder=embedder,
    )


def build_default_query_cache(embedder: IEmbedder) -> ISemanticCache:
    """Wires the semantic query cache from project configs.

    The embedder is local, so a cache lookup costs no hosted-model quota; only
    an actual miss does.
    """
    return SemanticQueryCache(
        embedder=embedder,
        store=QdrantQueryCacheStore(
            DBConfig.QDRANT_URL, CacheConfig.QUERY_CACHE_COLLECTION
        ),
        threshold=CacheConfig.QUERY_CACHE_THRESHOLD,
        ttl_seconds=CacheConfig.QUERY_CACHE_TTL_SECONDS,
        enabled=CacheConfig.QUERY_CACHE_ENABLED,
    )


class CompanyResearchAgent:
    """Runnable company research agent over the compiled graph.

    ``run`` consults the semantic query cache first, so a question that has
    already been answered (or a near-identical rewording) returns immediately
    without re-crawling or re-spending model quota. Set
    ``QUERY_CACHE_ENABLED=false`` to bypass it.
    """

    def __init__(
        self,
        components: AgentComponents | None = None,
        query_cache: ISemanticCache | None = None,
    ) -> None:
        self.components = components or build_default_components()
        self.query_cache = (
            query_cache
            if query_cache is not None
            else build_default_query_cache(self.components.embedder)
        )
        self.graph = build_graph(self.components)

    async def setup(self) -> None:
        """Prepares the vector collections used by retrieval and caching."""
        vector_store = getattr(self.components.store, "vector_store", None)
        if vector_store is not None:
            await vector_store.ensure_collection(DBConfig.VECTOR_SIZE)
        await self.query_cache.ensure_ready(DBConfig.VECTOR_SIZE)

    async def run(self, query: str) -> AgentState:
        """Answers one research query, reusing a cached answer when safe."""
        cached = await self.query_cache.lookup(query)
        if cached is not None:
            return {
                "query": query,
                "answer": cached.answer,
                "company_domain": cached.company_domain or None,
                "cache_hit": True,
            }

        state = await self.graph.ainvoke({"query": query})
        extracted = state.get("extracted")
        await self.query_cache.store(
            query,
            state.get("answer", ""),
            state.get("company_domain") or "",
            extracted.intent if extracted is not None else "",
        )
        return {**state, "cache_hit": False}

    async def close(self) -> None:
        """Releases the stores held by the graph and the query cache."""
        await asyncio.gather(
            self.components.store.close(),
            self.query_cache.close(),
            return_exceptions=True,
        )

