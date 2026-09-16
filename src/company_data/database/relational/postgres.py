import psycopg
from company_data_crawler.models.company_data import CompanyData

from company_data.database.base import IProfileStore, SourcedProfile
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class PostgresStore(IProfileStore):
    """PostgreSQL adapter: the relational system of record for company profiles.

    Every crawler source (craft, owler, ...) persists its own row keyed by
    (company_domain, source_name), so records from independent sources never
    overwrite or merge each other at rest. See schema.sql for the table
    definition.
    """

    def __init__(self, pg_connection_string: str) -> None:
        self.pg_conn_str = pg_connection_string

    async def store_profile(self, profile: CompanyData, source_name: str) -> None:
        """Upserts one source's record, leaving other sources' rows untouched."""
        pg_query = """
            INSERT INTO company_profiles
                (company_domain, source_name, company_name, profile_data)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (company_domain, source_name)
            DO UPDATE SET
                company_name = EXCLUDED.company_name,
                profile_data = EXCLUDED.profile_data,
                updated_at = CURRENT_TIMESTAMP;
        """
        # Bind a plain dict, not model_dump_json(): psycopg adapts dict -> JSONB
        # natively, whereas a raw string would fail PostgreSQL's text -> jsonb cast.
        # mode="json" converts datetimes/enums so JSONB serialization never chokes.
        json_payload = profile.model_dump(mode="json")

        async with await psycopg.AsyncConnection.connect(self.pg_conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    pg_query,
                    (
                        profile.company_domain,
                        source_name,
                        profile.company_name,
                        json_payload,
                    ),
                )
            await conn.commit()

        logger.info(
            f"Persisted {source_name} profile for {profile.company_name} to PostgreSQL."
        )

    async def fetch_source_profiles(self, company_domain: str) -> list[SourcedProfile]:
        """Returns every per-source record stored for the company."""
        query = """
            SELECT source_name, profile_data
            FROM company_profiles
            WHERE company_domain = %s
            ORDER BY updated_at DESC;
        """

        async with await psycopg.AsyncConnection.connect(self.pg_conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (company_domain,))
                rows = await cur.fetchall()

        return [
            SourcedProfile(
                source_name=row[0], profile=CompanyData.model_validate(row[1])
            )
            for row in rows
        ]

    async def close(self) -> None:
        """Connections are opened per operation, so nothing persistent to release."""
