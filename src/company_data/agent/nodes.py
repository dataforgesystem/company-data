"""Graph nodes for the company research agent.

Each factory binds the agent's components and returns an async LangGraph
node callable ``state -> partial state update``.
"""

import asyncio
from dataclasses import dataclass

from company_data_crawler.models.company_data import CompanyData

from company_data.agent.state import AgentState
from company_data.config.llm_configs import Prompts
from company_data.database.base import SourcedProfile
from company_data.llm.base import IEmbedder, ILLMProvider
from company_data.pipeline.interfaces.extractor import BaseExtractor
from company_data.pipeline.interfaces.merger import BaseMerger
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


@dataclass
class AgentComponents:
    """Everything the graph nodes need; injected, so any part is fakeable."""

    llm: ILLMProvider
    extractor: BaseExtractor
    merger: BaseMerger
    ingestion: object  # IngestionPipeline (kept loose for test doubles)
    store: object  # ICompanyStore (kept loose for test doubles)
    embedder: IEmbedder
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.5


def extract_intent_node(components: AgentComponents):
    async def extract_intent(state: AgentState) -> dict:
        """Turns the raw query into a capability-validated intent."""
        extracted = await asyncio.to_thread(
            components.extractor.extract_intent, state["query"]
        )
        return {"extracted": extracted}

    return extract_intent


def retrieve_company_node(components: AgentComponents):
    async def retrieve_company(state: AgentState) -> dict:
        """Finds a known company for the query via semantic vector lookup."""
        query_embedding = await asyncio.to_thread(
            components.embedder.embed, state["query"]
        )
        hits = await components.store.search_companies(
            query_embedding, top_k=components.retrieval_top_k
        )
        best = max(hits, key=lambda hit: hit.score, default=None)
        domain = (
            best.company_domain
            if best is not None and best.score >= components.retrieval_min_score
            else None
        )
        if domain is None:
            logger.info("Vector retrieval missed; the company will be ingested.")
        else:
            logger.info(
                f"Retrieved {domain} (score={best.score:.3f}, source={best.source_name})."
            )
        return {"company_domain": domain}

    return retrieve_company


def ensure_profiles_node(components: AgentComponents):
    async def ensure_profiles(state: AgentState) -> dict:
        """Loads per-source records, ingesting from the crawler on cache miss."""
        company_name = (state.get("extracted").company_name or "").strip()
        domain = state.get("company_domain")
        profiles: list[SourcedProfile] = []

        if domain:
            profiles = await components.store.fetch_source_profiles(domain)

        if not profiles:
            logger.info(
                f"No stored records for {company_name!r}; ingesting from crawler sources."
            )
            results = await components.ingestion.ingest(company_name)
            stored = [
                result
                for result in results
                if result.status == "stored" and result.company_domain
            ]
            if stored:
                domain = stored[0].company_domain
                profiles = await components.store.fetch_source_profiles(domain)

        return {"company_domain": domain, "source_profiles": profiles}

    return ensure_profiles


def merge_profile_node(components: AgentComponents):
    async def merge_profile(state: AgentState) -> dict:
        """Merges per-source records only when more than one source exists."""
        profiles = state.get("source_profiles") or []
        if not profiles:
            return {"merged_profile": None}
        if len(profiles) == 1:
            # Nothing to reconcile: the single record is used as-is (no LLM call).
            return {"merged_profile": profiles[0].profile}
        merged: CompanyData = await asyncio.to_thread(
            components.merger.merge_profiles, profiles, state.get("query")
        )
        return {"merged_profile": merged}

    return merge_profile


def synthesize_answer_node(components: AgentComponents):
    async def synthesize_answer(state: AgentState) -> dict:
        """Answers the question from the merged profile (RAG synthesis)."""
        profile = state.get("merged_profile")
        if profile is None:
            company = (state.get("extracted").company_name or "").strip()
            return {
                "answer": (
                    f"I could not find or collect a profile for '{company}'. "
                    "Try again later or rephrase the company name."
                )
            }
        prompt = Prompts.PROFILE_ANSWER_USER_PROMPT.format(
            profile_json=profile.model_dump_json(), query=state["query"]
        )
        answer = await asyncio.to_thread(
            components.llm.generate_text,
            prompt,
            Prompts.PROFILE_ANSWER_SYSTEM_PROMPT,
        )
        return {"answer": answer}

    return synthesize_answer


def respond_invalid_intent_node(components: AgentComponents):
    async def respond_invalid_intent(state: AgentState) -> dict:
        """Polite refusal when the query matches no crawler capability."""
        return {
            "answer": (
                "This request is outside the company data crawler's "
                "capabilities. I can look up company profiles by name or "
                "stock symbol and report their firmographic data."
            )
        }

    return respond_invalid_intent

