import psycopg
from company_data_crawler.models.company_data import CompanyData

from company_data.database.base import IProfileStore
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class PostgresStore(IProfileStore):
    """PostgreSQL adapter: the relational system of record for company profiles."""

    def __init__(self, pg_connection_string: str) -> None:
        self.pg_conn_str = pg_connection_string

    async def fetch_profile(self, company_id: str) -> CompanyData | None:
        """Queries PostgreSQL JSONB column natively for rapid lookup."""
        query = "SELECT profile_data FROM company_profiles WHERE company_id = %s;"

        async with await psycopg.AsyncConnection.connect(self.pg_conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (company_id,))
                row = await cur.fetchone()
                if row:
                    # Row data is automatically read as a Python dict from JSONB
                    return CompanyData.model_validate(row[0])
        return None

    async def store_profile(self, profile: CompanyData) -> None:
        """Stores the full, rich JSON structure cheaply inside PostgreSQL."""
        pg_query = """
            INSERT INTO company_profiles (company_domain, company_name, profile_data)
            VALUES (%s, %s, %s)
            ON CONFLICT (company_domain)
            DO UPDATE SET profile_data = EXCLUDED.profile_data, updated_at = CURRENT_TIMESTAMP;
        """
        # Bind a plain dict, not model_dump_json(): psycopg adapts dict -> JSONB
        # natively, whereas a raw string would fail PostgreSQL's text -> jsonb cast.
        json_payload = profile.model_dump()

        async with await psycopg.AsyncConnection.connect(self.pg_conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    pg_query,
                    (profile.company_domain, profile.company_name, json_payload),
                )
            await conn.commit()

        logger.info(f"Persisted profile for {profile.company_name} to PostgreSQL.")

    async def close(self) -> None:
        """Connections are opened per operation, so nothing persistent to release."""
