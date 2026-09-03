import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Pre-existing import cycle: interfaces.iconfig -> craft/__init__ ->
# base.scraper -> interfaces.iconfig. It only resolves when the craft package
# is imported first (existing tests rely on the same ordering), so do that here.
import craft  # noqa: F401

from interfaces.iconfig import IDatabaseConfig
from models.company_data import CompanyData

from storage.mongo_store import MongoDBStorage


class MongoDBStorageTest(unittest.TestCase):
    def _config(self, **overrides) -> IDatabaseConfig:
        kwargs = dict(
            driver="mongodb",
            name="companies",
            host="db.internal",
            port=27017,
            user="crawler",
            password="secret",
            authSource="admin",
        )
        kwargs.update(overrides)
        return IDatabaseConfig(**kwargs)

    def _company(self) -> CompanyData:
        return CompanyData(
            company_name="Stripe",
            company_domain="stripe.com",
            company_founded_year=2010,
            last_scraped_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )

    def test_connect_uses_dsn_and_extras_and_builds_collection(self):
        client_mock = MagicMock(name="client")
        db_mock = MagicMock(name="db")
        client_mock.__getitem__.return_value = db_mock

        with patch("storage.mongo_store.MongoClient", return_value=client_mock) as mongo_client:
            storage = MongoDBStorage(self._config())
            storage.connect()

        args, kwargs = mongo_client.call_args
        self.assertEqual(
            args[0], "mongodb://crawler:secret@db.internal:27017/companies"
        )
        # Extra config options (e.g. authSource) are forwarded to MongoClient.
        self.assertEqual(kwargs["authSource"], "admin")
        client_mock.__getitem__.assert_called_once_with("companies")
        db_mock.__getitem__.assert_called_once_with("company_data")
        self.assertIs(storage.company_data_collection, db_mock.__getitem__.return_value)

    def test_store_data_upserts_bson_safe_document(self):
        storage = MongoDBStorage(self._config())
        collection = MagicMock(name="collection")
        storage.company_data_collection = collection  # bypass connect()

        storage.store_data(self._company())

        kwargs = collection.update_one.call_args.kwargs
        self.assertEqual(kwargs["filter"], {"company_domain": "stripe.com"})
        self.assertTrue(kwargs["upsert"])

        payload = kwargs["update"]["$set"]
        # mode="json" must leave nothing BSON cannot encode (enums, datetimes).
        json.dumps(payload)  # must not raise
        self.assertEqual(payload["company_name"], "Stripe")
        self.assertEqual(payload["company_status"]["status"], "active")
        self.assertEqual(payload["last_scraped_at"], "2026-08-31T12:00:00Z")

    def test_store_data_upserts_for_every_company_data_instance(self):
        # A default CompanyData (with the auto-populated company_status enum)
        # must be storable without any extra serialization hints.
        storage = MongoDBStorage(self._config())
        collection = MagicMock(name="collection")
        storage.company_data_collection = collection

        storage.store_data(
            CompanyData(
                company_name="Default",
                company_domain="default.com",
                company_founded_year=None,
            )
        )

        payload = collection.update_one.call_args.kwargs["update"]["$set"]
        json.dumps(payload)  # must not raise
        self.assertEqual(payload["company_status"]["status"], "active")


if __name__ == "__main__":
    unittest.main()