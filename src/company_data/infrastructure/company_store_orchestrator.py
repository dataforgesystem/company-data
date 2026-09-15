import asyncio

from company_data_crawler.models.company_data import CompanyData

from company_data.interfaces.company_store import (
    ICompanyStore,
    IProfileStore,
    IVectorStore,
)
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class CompanyStoreOrchestrator(ICompanyStore):
    """Fans store operations out to PostgreSQL and Qdrant concurrently.

    - Writes: runs the JSONB upsert and the vector upsert simultaneously via
      asyncio.gather, so neither engine waits on the other.
    - Reads: served from PostgreSQL, the system of record.
    """

    def __init__(self, profile_store: IProfileStore, vector_store: IVectorStore) -> None:
        self.profile_store = profile_store
        self.vector_store = vector_store

    async def fetch_profile(self, company_id: str) -> CompanyData | None:
        """Delegates lookup to the PostgreSQL profile store."""
        return await self.profile_store.fetch_profile(company_id)

    async def store_and_sync_profile(
        self, profile: CompanyData, embedding: list[float]
    ) -> None:
        """Executes both storage writes concurrently across the two engines."""
        results = await asyncio.gather(
            self.profile_store.store_profile(profile),
            self.vector_store.index_profile(profile, embedding),
            return_exceptions=True,
        )

        # return_exceptions=True makes gather wait for BOTH writes to settle,
        # so a failure on one engine never silently cancels the other one.
        failures = [result for result in results if isinstance(result, BaseException)]
        for failure in failures:
            logger.error(
                f"Profile sync failure for {profile.company_name}: {failure!r}"
            )

        if failures:
            raise failures[0]

        logger.info(
            f"Successfully synchronized {profile.company_name} across SQL and Vector spaces."
        )

    async def close(self) -> None:
        """Shuts both underlying clients down concurrently."""
        await asyncio.gather(self.profile_store.close(), self.vector_store.close())