import unittest

# Pre-existing import cycle: interfaces.iconfig -> craft/__init__ ->
# base.scraper -> interfaces.iconfig. It only resolves when the craft package
# is imported first (existing tests rely on the same ordering), so do that here.
import craft  # noqa: F401

from base.storage import DataStorage
from company_crawler import (
    AVAILABLE_STORAGES,
    IDatabaseConfig,
    MongoDBStorage,
    PostgresUpdateResult,
    PostgreSQLStorage,
    get_storage,
)


class CompanyCrawlerPackageTest(unittest.TestCase):
    def test_package_exports_storage_backends(self):
        # Smoke test: the root package re-exports both storage backends.
        self.assertIsNotNone(MongoDBStorage)
        self.assertIsNotNone(PostgreSQLStorage)
        self.assertIsNotNone(PostgresUpdateResult)
        self.assertIsNotNone(IDatabaseConfig)
        self.assertIsNotNone(get_storage)

    def test_registry_maps_drivers_to_storage_classes(self):
        self.assertEqual(
            AVAILABLE_STORAGES,
            {
                "mongodb": MongoDBStorage,
                "postgresql": PostgreSQLStorage,
            },
        )

    def test_get_storage_returns_mongo_backend(self):
        storage = get_storage("MongoDB", name="companies")  # case-insensitive

        self.assertIsInstance(storage, MongoDBStorage)
        self.assertIsInstance(storage, DataStorage)
        self.assertEqual(storage.config.driver, "mongodb")

    def test_get_storage_returns_postgres_backend(self):
        storage = get_storage("PostgreSQL", name="companies")  # case-insensitive

        self.assertIsInstance(storage, PostgreSQLStorage)
        self.assertIsInstance(storage, DataStorage)
        self.assertEqual(storage.config.driver, "postgresql")

    def test_get_storage_accepts_prebuilt_config(self):
        config = IDatabaseConfig(driver="postgresql", name="companies")

        storage = get_storage("postgresql", config=config)

        self.assertIsInstance(storage, PostgreSQLStorage)
        self.assertIs(storage.config, config)

    def test_get_storage_forwards_config_kwargs(self):
        storage = get_storage(
            "mongodb", name="companies", host="db.internal", port=27017
        )

        self.assertEqual(storage.config.name, "companies")
        self.assertEqual(storage.config.host, "db.internal")
        self.assertEqual(storage.config.port, 27017)
        self.assertEqual(storage.config.dsn, "mongodb://db.internal:27017/companies")

    def test_get_storage_accepts_custom_driver_via_prebuilt_config(self):
        # The "driver" argument selects the backend; a custom IDatabaseConfig
        # driver (e.g. SQLAlchemy style) goes through a pre-built config.
        config = IDatabaseConfig(driver="postgresql+psycopg", name="companies")

        storage = get_storage("postgresql", config=config)

        self.assertIsInstance(storage, PostgreSQLStorage)
        self.assertEqual(storage.config.driver, "postgresql+psycopg")

    def test_get_storage_rejects_unknown_driver(self):
        with self.assertRaises(ValueError):
            get_storage("oracle", name="companies")


if __name__ == "__main__":
    unittest.main()