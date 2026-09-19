from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from company_data_crawler.models.company_data import CompanyData


@dataclass(frozen=True)
class SourcedProfile:
    """One crawled record together with the crawler source that produced it."""

    source_name: str
    profile: CompanyData

    def to_dict(self) -> dict:
        """JSON-ready form for serializing agent state (see ``tester.py``)."""
        return {
            "source_name": self.source_name,
            "profile": self.profile.model_dump(mode="json"),
        }


@dataclass(frozen=True)
class VectorHit:
    """One semantic search hit from the vector index."""

    company_domain: str
    company_name: str
    source_name: str
    score: float


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
    async def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        source_names: Sequence[str] | None = None,
    ) -> list["VectorHit"]:
        """Returns the closest indexed company points (semantic lookup).

        ``source_names`` optionally restricts hits to the given crawler
        sources; ``None`` searches every indexed source.
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
    async def search_companies(
        self,
        embedding: list[float],
        top_k: int = 5,
        source_names: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Semantic company lookup delegated to the vector index.

        ``source_names`` optionally restricts hits to the given crawler
        sources; ``None`` searches every indexed source.
        """

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
