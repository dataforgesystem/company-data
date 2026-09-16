import uuid

from company_data_crawler.models.company_data import CompanyData
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from company_data.database.base import IVectorStore
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class QdrantStore(IVectorStore):
    """Qdrant adapter: the vector index used for semantic company lookup."""

    def __init__(self, qdrant_url: str, collection_name: str = "companies") -> None:
        self.client = AsyncQdrantClient(url=qdrant_url)
        self.collection_name = collection_name

    async def index_profile(self, profile: CompanyData, embedding: list[float]) -> None:
        """Pushes the generated vector directly into the Qdrant index."""
        # uuid5 derives a stable, process-independent id from the company domain,
        # so re-syncing the same company upserts its point instead of duplicating
        # it (built-in hash() is randomized per interpreter run).
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, profile.company_domain))

        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "company_domain": profile.company_domain,
                        "company_name": profile.company_name,
                    },
                )
            ],
        )
        logger.info(f"Indexed vector for {profile.company_name} in Qdrant.")

    async def close(self) -> None:
        """Releases the underlying async HTTP session."""
        await self.client.close()
