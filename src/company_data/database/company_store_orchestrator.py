import asyncio

from company_data_crawler.models.company_data import CompanyData

from company_data.database.base import (
    ICompanyStore,
    IProfileStore,
    IVectorStore,
    SourcedProfile,
)
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class CompanyStoreOrchestrator(ICompanyStore):
    """Fans per-source store operations out to PostgreSQL and Qdrant.

    The crawler collects the same company from independent sources (craft,
    owler, ...). Records are stored per source and never conflated or merged
    at rest; reconciling them into a single profile is an explicit, on-demand
    step performed by an LLM merger (see pipeline.llm_merger) only when a
    consumer requires one.

    - Writes: the source's JSONB row and its vector point are independent
      per-source writes, so both engines run concurrently via asyncio.gather.
    - Reads: per-source records from PostgreSQL, the system of record.
    """

    def __init__(self, profile_store: IProfileStore, vector_store: IVectorStore) -> None:
        self.profile_store = profile_store
        self.vector_store = vector_store

    async def fetch_source_profiles(self, company_domain: str) -> list[SourcedProfile]:
        """Delegates lookup to the PostgreSQL profile store (per-source records)."""
        return await self.profile_store.fetch_source_profiles(company_domain)

    async def store_and_sync_profile(
        self, profile: CompanyData, embedding: list[float], source_name: str
    ) -> None:
        """Stores one source's record in both engines, untouched by other sources."""
        results = await asyncio.gather(
            self.profile_store.store_profile(profile, source_name),
            self.vector_store.index_profile(profile, embedding, source_name),
            return_exceptions=True,
        )

        # return_exceptions=True makes gather wait for BOTH writes to settle,
        # so a failure on one engine never silently cancels the other one.
        failures = [result for result in results if isinstance(result, BaseException)]
        for failure in failures:
            logger.error(
                f"Profile sync failure for {profile.company_name} "
                f"({source_name}): {failure!r}"
            )

        if failures:
            raise failures[0]

        logger.info(
            f"Successfully synchronized {profile.company_name} ({source_name}) "
            f"across SQL and Vector spaces."
        )

    async def close(self) -> None:
        """Shuts both underlying clients down concurrently."""
        await asyncio.gather(self.profile_store.close(), self.vector_store.close())