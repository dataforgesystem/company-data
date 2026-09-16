import os


class DBConfig:
    """Database connection settings, overridable via environment variables."""

    PG_CONNECTION_STRING = os.getenv(
        "PG_CONNECTION_STRING",
        "postgresql://postgres:test123@localhost:5432/company_data",
    )
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "companies")
    # Dimensionality of the embedding model (nomic-embed-text -> 768).
    VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "768"))
