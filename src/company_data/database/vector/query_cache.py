import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from company_data.cache.interfaces import IQueryCacheStore, QueryCacheHit
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class QdrantQueryCacheStore(IQueryCacheStore):
    """Qdrant adapter for cached query/answer pairs.

    Kept separate from the company index: a cache point is disposable data with
    a different payload shape and its own collection, so it must never be
    mixed into semantic company retrieval.
    """

    def __init__(self, qdrant_url: str, collection_name: str = "query_cache") -> None:
        self.client = AsyncQdrantClient(url=qdrant_url)
        self.collection_name = collection_name

    async def ensure_collection(self, vector_size: int) -> None:
        """Creates the cache collection when missing (cosine, like the index)."""
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info(
                f"Created Qdrant query cache collection "
                f"'{self.collection_name}' (dim={vector_size})."
            )

    async def search(
        self, embedding: list[float], top_k: int = 1
    ) -> list[QueryCacheHit]:
        """Returns the closest cached queries, newest payload data included."""
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit=top_k,
            with_payload=True,
        )
        hits: list[QueryCacheHit] = []
        for point in response.points:
            payload = point.payload or {}
            hits.append(
                QueryCacheHit(
                    query=str(payload.get("query", "")),
                    answer=str(payload.get("answer", "")),
                    company_domain=str(payload.get("company_domain", "")),
                    intent=str(payload.get("intent", "")),
                    created_at=float(payload.get("created_at") or 0.0),
                    score=float(point.score or 0.0),
                )
            )
        return hits

    async def upsert(
        self, point_id: str, embedding: list[float], payload: dict
    ) -> None:
        """Stores one cached query/answer point, replacing an equal point id."""
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=str(uuid.UUID(point_id)),
                    vector=embedding,
                    payload=payload,
                )
            ],
        )

    async def close(self) -> None:
        """Releases the underlying async HTTP session."""
        await self.client.close()