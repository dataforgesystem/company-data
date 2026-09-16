from abc import ABC, abstractmethod

from company_data_crawler.models.company_data import CompanyData


class IProfileStore(ABC):
    """Contract for the relational system of record (PostgreSQL JSONB)."""

    @abstractmethod
    async def fetch_profile(self, company_id: str) -> CompanyData | None:
        """
        Queries the database to retrieve a fully unified, pre-merged profile.
        Returns None if the entity does not exist (Cache Miss).
        """

    @abstractmethod
    async def store_profile(self, profile: CompanyData) -> None:
        """
        Writes the complete, nested JSON payload cheaply to a PostgreSQL JSONB column.
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases any connections or clients held by the store."""


class IVectorStore(ABC):
    """Contract for the vector index (Qdrant) used for semantic retrieval."""

    @abstractmethod
    async def index_profile(self, profile: CompanyData, embedding: list[float]) -> None:
        """
        Indexes the vector coordinates into Qdrant alongside the reference company payload.
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases any connections or clients held by the store."""


class ICompanyStore(ABC):
    """
    Composite contract consumed by the pipeline.

    A single call fans out to the profile store and the vector store so both
    engines are written to simultaneously.
    """

    @abstractmethod
    async def fetch_profile(self, company_id: str) -> CompanyData | None:
        """
        Queries the database to retrieve a fully unified, pre-merged profile.
        Returns None if the entity does not exist (Cache Miss).
        """

    @abstractmethod
    async def store_and_sync_profile(
        self, profile: CompanyData, embedding: list[float]
    ) -> None:
        """
        Executes the 'Data Syncer' operation concurrently:
        1. Writes the complete, nested JSON payload to a PostgreSQL JSONB column.
        2. Indexes the vector coordinates into Qdrant alongside the reference company_id.
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases resources held by the underlying stores."""
