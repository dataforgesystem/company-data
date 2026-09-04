import json
import sys
import unittest
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import MagicMock, patch

# Pre-existing import cycle: interfaces.iconfig -> craft/__init__ ->
# base.scraper -> interfaces.iconfig. It only resolves when the craft package
# is imported first (existing tests rely on the same ordering), so do that here.
import craft  # noqa: F401

from interfaces.iconfig import IDatabaseConfig
from models.company_data import CompanyData

try:
    import psycopg  # noqa: F401
except ImportError:  # pragma: no cover - only hit when the driver is missing
    # The unit tests never open a real connection, so a tiny stub is enough to
    # import the storage module without the psycopg dependency installed.
    psycopg = ModuleType("psycopg")
    psycopg.Connection = MagicMock(name="psycopg.Connection")
    psycopg.Cursor = MagicMock(name="psycopg.Cursor")
    psycopg.connect = MagicMock(name="psycopg.connect")
    psycopg_types = ModuleType("psycopg.types")
    psycopg_types_json = ModuleType("psycopg.types.json")

    class Jsonb:
        def __init__(self, obj):
            self.obj = obj

    psycopg_types_json.Jsonb = Jsonb
    psycopg_types.json = psycopg_types_json
    psycopg.types = psycopg_types
    sys.modules.setdefault("psycopg", psycopg)
    sys.modules.setdefault("psycopg.types", psycopg_types)
    sys.modules.setdefault("psycopg.types.json", psycopg_types_json)

from storage.postgres_store import PostgresUpdateResult, PostgreSQLStorage


class PostgreSQLStorageTest(unittest.TestCase):
    def _config(self, **overrides) -> IDatabaseConfig:
        kwargs = dict(
            driver="postgresql",
            name="companies",
            host="db.internal",
            port=5432,
            user="crawler",
            password="secret",
            retryWrites="true",  # Mongo-style extra must be ignored
            connect_timeout=10,
        )
        kwargs.update(overrides)
        return IDatabaseConfig(**kwargs)

    def _connected_storage(self, config):
        connection = MagicMock(name="connection")
        cursor = MagicMock(name="cursor")
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch("psycopg.connect", return_value=connection) as connect_mock:
            storage = PostgreSQLStorage(config)
            storage.connect()
        return storage, connect_mock, connection, cursor

    def _company(self) -> CompanyData:
        return CompanyData(
            company_name="Stripe",
            company_domain="stripe.com",
            company_founded_year=2010,
            last_scraped_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )

    def test_connect_opens_connection_with_normalized_dsn(self):
        _, connect_mock, connection, _ = self._connected_storage(self._config())

        args, kwargs = connect_mock.call_args
        self.assertEqual(
            args[0], "postgresql://crawler:secret@db.internal:5432/companies"
        )
        self.assertTrue(kwargs["autocommit"])
        # Valid libpq extras are forwarded...
        self.assertEqual(kwargs["connect_timeout"], 10)
        # ...while driver-specific extras are dropped.
        self.assertNotIn("retryWrites", kwargs)

        create_table_sql = connection.execute.call_args[0][0]
        self.assertIn("CREATE TABLE IF NOT EXISTS company_data", create_table_sql)
        self.assertIn("company_domain TEXT PRIMARY KEY", create_table_sql)
        self.assertIn("data JSONB NOT NULL", create_table_sql)

    def test_connect_normalizes_sqlalchemy_style_driver(self):
        config = self._config(driver="postgresql+psycopg")
        _, connect_mock, _, _ = self._connected_storage(config)

        args, _ = connect_mock.call_args
        self.assertTrue(args[0].startswith("postgresql://"))

    def test_connect_supports_custom_table_via_extra_options(self):
        config = self._config(table="companies")
        storage, _, connection, _ = self._connected_storage(config)

        create_table_sql = connection.execute.call_args[0][0]
        self.assertIn("CREATE TABLE IF NOT EXISTS companies", create_table_sql)
        self.assertEqual(storage.company_data_table, "companies")

    def test_connect_rejects_invalid_table_name(self):
        config = self._config(table="company; DROP TABLE company_data")

        # Patch the connection so the validation error is what's exercised.
        with patch("psycopg.connect"):
            with self.assertRaises(ValueError):
                PostgreSQLStorage(config).connect()

    def test_store_data_upserts_json_document_for_new_company(self):
        storage, _, _, cursor = self._connected_storage(self._config())
        cursor.fetchone.return_value = (True,)
        cursor.rowcount = 1

        result = storage.store_data(self._company())

        sql, params = cursor.execute.call_args[0]
        self.assertIn("INSERT INTO company_data (company_domain, data)", sql)
        self.assertIn("ON CONFLICT (company_domain)", sql)
        self.assertIn("DO UPDATE SET data = EXCLUDED.data", sql)
        self.assertEqual(params[0], "stripe.com")
        payload = params[1].obj
        self.assertEqual(payload["company_name"], "Stripe")
        # model_dump(mode="json") keeps the payload JSONB-compatible.
        self.assertEqual(payload["last_scraped_at"], "2026-08-31T12:00:00Z")
        json.dumps(payload)  # must not raise

        self.assertIsInstance(result, PostgresUpdateResult)
        self.assertEqual(result.upserted_id, "stripe.com")
        self.assertEqual(result.matched_count, 0)
        self.assertEqual(result.rowcount, 1)
        self.assertTrue(result.acknowledged)

    def test_store_data_reports_update_for_existing_company(self):
        storage, _, _, cursor = self._connected_storage(self._config())
        cursor.fetchone.return_value = (False,)
        cursor.rowcount = 1

        result = storage.store_data(self._company())

        self.assertEqual(result.matched_count, 1)
        self.assertIsNone(result.upserted_id)
        self.assertEqual(result.rowcount, 1)

    def test_close_closes_connection(self):
        storage, _, connection, _ = self._connected_storage(self._config())

        storage.close()

        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()