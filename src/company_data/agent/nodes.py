"""Graph nodes for the company research agent.

Each factory binds the agent's components and returns an async LangGraph
node callable ``state -> partial state update``.
"""

import asyncio
from dataclasses import dataclass

from company_data_crawler.models.company_data import CompanyData

from company_data.agent.state import AgentState
from company_data.config.crawler_configs import MergeConfig
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


def _requested_names(state: AgentState) -> list[str]:
    """Company names the query asked for, in mention order.

    Prefers the multi-company field; falls back to the legacy single alias,
    so states built by older callers still resolve.
    """
    extracted = state.get("extracted")
    names = list(state.get("company_names") or [])
    if not names and extracted is not None:
        names = list(extracted.company_names or [])
        if not names and (extracted.company_name or "").strip():
            names = [extracted.company_name.strip()]
    return [name for name in (name.strip() for name in names) if name]


def _same_company_name(requested_name: str, hit_name: str) -> bool:
    """Avoid treating semantic similarity as proof of company identity."""
    return " ".join(requested_name.casefold().split()) == " ".join(
        hit_name.casefold().split()
    )


def extract_intent_node(components: AgentComponents):
    async def extract_intent(state: AgentState) -> dict:
        """Turns the raw query into a capability-validated intent."""
        extracted = await asyncio.to_thread(
            components.extractor.extract_intent, state["query"]
        )
        names = [
            name
            for name in (name.strip() for name in (extracted.company_names or []))
            if name
        ]
        return {"extracted": extracted, "company_names": names}

    return extract_intent


def retrieve_company_node(components: AgentComponents):
    async def retrieve_company(state: AgentState) -> dict:
        """Finds a known company per requested name via semantic vector lookup.

        Retrieval is scoped to the active merge strategy's sources, so under
        a single-source strategy a company is never resolved from another
        source's (possibly stale) point.
        """
        names = _requested_names(state)
        allowed_sources = MergeConfig.read_sources()

        async def _resolve_one(name: str) -> str | None:
            query_embedding = await asyncio.to_thread(
                components.embedder.embed, f"{name} {state['query']}"
            )
            hits = await components.store.search_companies(
                query_embedding,
                top_k=components.retrieval_top_k,
                source_names=allowed_sources,
            )
            matching_hits = [
                hit for hit in hits if _same_company_name(name, hit.company_name)
            ]
            best = max(matching_hits, key=lambda hit: hit.score, default=None)
            if best is not None and best.score >= components.retrieval_min_score:
                logger.info(
                    f"Retrieved {name} -> {best.company_domain} "
                    f"(score={best.score:.3f}, source={best.source_name})."
                )
                return best.company_domain
            logger.info(f"Vector retrieval missed for {name!r}; it will be ingested.")
            return None

        domains = [await _resolve_one(name) for name in names]
        return {
            "company_domains": domains,
            # Legacy mirror: first company, as before.
            "company_domain": domains[0] if domains else None,
        }

    return retrieve_company


def ensure_profiles_node(components: AgentComponents):
    async def ensure_profiles(state: AgentState) -> dict:
        """Loads per-source records per company, ingesting on cache miss.

        Reads are scoped to the active merge strategy: single-source
        strategies (``off``/``preferred``) load only the preferred source's
        row, so a stale row from another source can never leak into the
        answer. Multi-source strategies (``union``/``llm``) load everything.
        """
        names = _requested_names(state)
        domains = list(state.get("company_domains") or [])
        while len(domains) < len(names):
            domains.append(None)

        async def _ensure_one(index: int) -> tuple[str | None, list[SourcedProfile]]:
            name = names[index]
            domain = domains[index]
            profiles: list[SourcedProfile] = []

            if domain:
                profiles = _strategy_records(
                    await components.store.fetch_source_profiles(domain)
                )

            # Preferred row missing (or only other sources exist): ingest the
            # preferred source rather than serving a stale foreign row. Under
            # the default scrape routing the ingestion covers exactly the
            # preferred source, so this either stores it or proves it missing.
            if not profiles:
                logger.info(
                    f"No {MergeConfig.PREFERRED_SOURCE!r} record for {name!r}; "
                    "ingesting the preferred source."
                )
                results = await components.ingestion.ingest(name)
                stored = [
                    result
                    for result in results
                    if result.status == "stored" and result.company_domain
                ]
                if stored:
                    domain = stored[0].company_domain
                    profiles = _strategy_records(
                        await components.store.fetch_source_profiles(domain)
                    )

            return domain, profiles

        resolved = [await _ensure_one(index) for index in range(len(names))]
        domains = [domain for domain, _ in resolved]
        per_company = [profiles for _, profiles in resolved]
        return {
            "company_domains": domains,
            # Per-company per-source records, same order as the requested
            # names — the provenance the merge node consumes.
            "company_source_profiles": per_company,
            # Flattened view across EVERY requested company (not just the
            # first), so serialized states show where all data came from.
            "source_profiles": [
                profile for profiles in per_company for profile in profiles
            ],
            # Legacy mirror: first company, as before.
            "company_domain": domains[0] if domains else None,
        }

    return ensure_profiles


def merge_profile_node(components: AgentComponents):
    async def merge_profile(state: AgentState) -> dict:
        """Resolves one profile per requested company via the merger.

        Records come from ``company_source_profiles`` (populated by
        ``ensure_profiles_node``), so this node never re-fetches or
        re-ingests what the ensure step already resolved. The merger runs
        per company only when it has more than one source record; a single
        record is used as-is with no model call.
        """
        names = _requested_names(state)
        domains = list(state.get("company_domains") or [])
        while len(domains) < len(names):
            domains.append(None)
        per_company_state = state.get("company_source_profiles")
        legacy_first = state.get("source_profiles") or []

        async def _resolve_one(index: int) -> CompanyData | None:
            if per_company_state is not None and index < len(per_company_state):
                profiles = list(per_company_state[index] or [])
            elif index == 0 and legacy_first:
                # Legacy fallback: state built without ensure_profiles_node.
                profiles = list(legacy_first)
            else:
                profiles = await _profiles_for(index, domains, names)
            if not profiles:
                return None
            if len(profiles) == 1:
                # Nothing to reconcile: single record used as-is (no LLM call).
                return profiles[0].profile
            return await asyncio.to_thread(
                components.merger.merge_profiles, profiles, state.get("query")
            )

        async def _profiles_for(
            index: int, domains: list, names: list[str]
        ) -> list[SourcedProfile]:
            domain = domains[index]
            profiles = (
                _strategy_records(await components.store.fetch_source_profiles(domain))
                if domain
                else []
            )
            if not profiles:
                logger.info(
                    f"No {MergeConfig.PREFERRED_SOURCE!r} record for {names[index]!r}; "
                    "ingesting the preferred source."
                )
                results = await components.ingestion.ingest(names[index])
                stored = [
                    result
                    for result in results
                    if result.status == "stored" and result.company_domain
                ]
                if stored:
                    domains[index] = stored[0].company_domain
                    profiles = _strategy_records(
                        await components.store.fetch_source_profiles(domains[index])
                    )
            return profiles

        resolved = [await _resolve_one(index) for index in range(len(names))]
        return {
            "company_domains": domains,
            "company_profiles": resolved,
            # Legacy mirrors: first company, as before.
            "company_domain": domains[0] if domains else None,
            "merged_profile": resolved[0] if resolved else None,
        }

    return merge_profile


def _strategy_records(records: list[SourcedProfile]) -> list[SourcedProfile]:
    """Scopes fetched records to what the active merge strategy consumes.

    Single-source strategies keep only the preferred source's row — strictly,
    with no fallback to other sources. If the preferred row is absent the
    caller treats it as "not stored" and ingests the preferred source, so a
    stale row from another source can never leak into the answer and reads
    can never disagree with what ingestion scraped. Multi-source strategies
    keep every record.
    """
    if MergeConfig.needs_all_sources() or not records:
        return records
    wanted = (MergeConfig.PREFERRED_SOURCE or "").strip().lower()
    return [
        record
        for record in records
        if (record.source_name or "").strip().lower() == wanted
    ]


def synthesize_answer_node(components: AgentComponents):
    async def synthesize_answer(state: AgentState) -> dict:
        """Answers the question from the resolved profile(s) (RAG synthesis)."""
        profiles = list(state.get("company_profiles") or [])
        if not profiles and state.get("merged_profile") is not None:
            profiles = [state.get("merged_profile")]
        names = _requested_names(state)
        answered = [
            (name, profile) for name, profile in zip(names, profiles) if profile
        ]
        if not answered:
            missing = ", ".join(names) if names else "the company"
            return {
                "answer": (
                    f"I could not find or collect a profile for '{missing}'. "
                    "Try again later or rephrase the company name."
                )
            }
        if len(answered) == 1:
            _name, profile = answered[0]
            prompt = Prompts.PROFILE_ANSWER_USER_PROMPT.format(
                profile_json=profile.model_dump_json(), query=state["query"]
            )
        else:
            joined = "\n\n".join(
                f"Company: {name}\n{profile.model_dump_json()}"
                for name, profile in answered
            )
            prompt = Prompts.PROFILE_MULTI_ANSWER_USER_PROMPT.format(
                profiles_json=joined, query=state["query"]
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
        """Polite refusal when the query matches no crawler capability.

        Distinguishes an extraction miss (valid intent, but no company name
        survived extraction) from a genuinely out-of-scope request, so the
        user gets an actionable message instead of a misleading one.
        """
        extracted = state.get("extracted")
        if extracted is not None and extracted.is_valid:
            return {
                "answer": (
                    "I understood your question "
                    f"({extracted.intent!r}) but could not tell which company "
                    "it is about. Please rephrase with the company name "
                    "spelled out, e.g. 'Who are the competitors of Google?'."
                )
            }
        return {
            "answer": (
                "This request is outside the company data crawler's "
                "capabilities. I can look up company profiles by name or "
                "stock symbol and report their firmographic data."
            )
        }

    return respond_invalid_intent
