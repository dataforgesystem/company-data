from abc import ABC, abstractmethod
from dataclasses import dataclass

from company_data_crawler.models.company_data import CompanyData


@dataclass(frozen=True)
class SourcedProfile:
    """One crawled record together with the crawler source that produced it."""

    source_name: str
    profile: CompanyData


class IProfileStore(ABC):
    """Contract for the relational system of record (PostgreSQL JSONB).

    The crawler collects the same company from independent sources (craft,
    owler, ...), so every source persists its own row. Records are never
    merged at rest; reconciling them into one profile is an explicit,
    on-demand step done by an LLM merger in the pipeline layer.
    """

    @abstractmethod
    async def store_profile(self, profile: CompanyData, source_name: str) -> None:
        """
        Upserts one source's record for a company, leaving other sources'
        rows for the same company untouched.
        """

    @abstractmethod
    async def fetch_source_profiles(self, company_domain: str) -> list[SourcedProfile]:
        """
        Returns every per-source record stored for the company.
        Returns an empty list if the entity does not exist (Cache Miss).
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases any connections or clients held by the store."""


class IVectorStore(ABC):
    """Contract for the vector index (Qdrant) used for semantic retrieval."""

    @abstractmethod
    async def index_profile(
        self, profile: CompanyData, embedding: list[float], source_name: str
    ) -> None:
        """
        Indexes one source's vector coordinates into Qdrant alongside a
        payload that identifies the company and the crawler source.
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases any connections or clients held by the store."""


class ICompanyStore(ABC):
    """
    Composite contract consumed by the pipeline.

    Writes fan out to both engines per source; reads return per-source
    records so callers decide when (and how) to reconcile them.
    """

    @abstractmethod
    async def fetch_source_profiles(self, company_domain: str) -> list[SourcedProfile]:
        """Returns every per-source record stored for the company."""

    @abstractmethod
    async def store_and_sync_profile(
        self, profile: CompanyData, embedding: list[float], source_name: str
    ) -> None:
        """
        Executes the 'Data Syncer' operation concurrently:
        1. Upserts the source's own record into PostgreSQL (per-source row).
        2. Indexes that same source's vector into Qdrant (per-source point).
        """

    @abstractmethod
    async def close(self) -> None:
        """Releases resources held by the underlying stores."""
