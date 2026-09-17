"""Ingestion pipeline: crawl a company from every source, embed, store per source.

Per source (craft, owler, ...): search -> scrape -> embed -> store. Records
are written as separate per-source rows/points (no merging at rest); the
on-demand LLM merger reconciles them only when a consumer needs a unified
profile.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from company_data_crawler import CompanyData, CompanyDataCrawler, ICrawlerConfig
from company_data_crawler.sources.registry import SourceRegistry

from company_data.config.crawler_configs import CrawlerConfig
from company_data.database.company_store_orchestrator import CompanyStoreOrchestrator
from company_data.llm.base import IEmbedder
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()

# Importing a provider module runs its @SourceRegistry.register decorator.
_SOURCE_MODULES: dict[str, str] = {
    "craft": "company_data_crawler.sources.craft.provider",
    "owler": "company_data_crawler.sources.owler.provider",
}


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of ingesting one company from one crawler source."""

    source_name: str
    status: str  # "stored" | "no_match" | "no_profile" | "failed"
    company_domain: str
    detail: str


class IngestionPipeline:
    """Crawls one company through every configured source and stores it.

    Each source's record is embedded from a compact text summary and written
    to both engines via the store orchestrator, keeping sources separate.
    """

    def __init__(
        self,
        store: CompanyStoreOrchestrator,
        embedder: IEmbedder,
        sources: Sequence[str] = ("craft", "owler"),
        crawler_config: ICrawlerConfig | None = None,
        cache_dir: str | None = CrawlerConfig.CACHE_DIR,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.sources = tuple(sources)
        self.crawler = CompanyDataCrawler(
            config=crawler_config or ICrawlerConfig(), cache_dir=cache_dir
        )
        self._register_available_sources()

    def _register_available_sources(self) -> None:
        """Import provider modules so their sources self-register; skip broken ones."""
        import importlib

        for name, module in _SOURCE_MODULES.items():
            try:
                importlib.import_module(module)
            except Exception as exc:  # optional Selenium deps may be missing
                logger.warning(f"Source '{name}' unavailable, skipping: {exc!r}")

    async def ingest(self, company_name: str) -> list[IngestionResult]:
        """Ingest ``company_name`` from every available source."""
        results: list[IngestionResult] = []
        for source in self.sources:
            results.append(await self._ingest_from_source(company_name, source))
        return results

    async def _ingest_from_source(
        self, company_name: str, source: str
    ) -> IngestionResult:
        try:
            matches = await asyncio.to_thread(
                self.crawler.search_company, company_name, source=source
            )
            if not matches:
                return IngestionResult(source, "no_match", "", "No search results.")

            profile = await asyncio.to_thread(
                self.crawler.get_company_data,
                self._best_match(matches, company_name).source_url,
                source=source,
            )
            if profile is None:
                return IngestionResult(
                    source, "no_profile", "", "Page could not be parsed."
                )

            embedding = await asyncio.to_thread(
                self.embedder.embed, self._embedding_text(profile)
            )
            await self.store.store_and_sync_profile(
                profile, embedding, source
            )
            return IngestionResult(
                source, "stored", profile.company_domain, profile.company_name
            )
        except Exception as exc:
            logger.error(f"Ingestion failed for {source}: {exc!r}")
            return IngestionResult(source, "failed", "", repr(exc))

    @staticmethod
    def _best_match(matches: Sequence, company_name: str):
        """Exact name match when present, else the top-ranked suggestion."""
        lowered = company_name.strip().lower()
        for match in matches:
            if match.company_name.strip().lower() == lowered:
                return match
        return matches[0]

    @staticmethod
    def _embedding_text(profile: CompanyData) -> str:
        """Compact deterministic text summary of a profile for embedding."""
        parts: list[str] = [
            profile.company_name,
            profile.company_domain,
            profile.company_description or "",
        ]
        parts += list(profile.company_industries)
        parts += [f"{e.name} ({e.title})" for e in profile.key_executives]
        parts += [
            f"{f.funding_round}: {f.funding_amount}"
            for f in profile.company_funding_info
            if f.funding_round
        ]
        return " | ".join(part for part in parts if part)
