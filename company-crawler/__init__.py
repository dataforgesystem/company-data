"""
Company Crawler - A comprehensive library for searching and scraping company data from multiple sources.

This module provides unified access to company data services from various sources:
  - craft: Craft.co scraping and searching services
  - (Additional sources can be added as plugins)

Available Services:
  - Search: Find companies by name or stock ticker
  - Scraping: Scrape and parse company pages
  - Storage: Persist company data to MongoDB or PostgreSQL
  - Exporting: Export data in various formats (CSV, JSON, Parquet)

Quick Start:
    # Using Craft source (default)
    from company_crawler.craft import create_search_service, create_scraping_service
    
    search_service = create_search_service()
    scraping_service = create_scraping_service()
    
    # Or access services through source-specific imports
    from company_crawler.craft import CraftCompanySearchingService, CraftCompanyPageScrapingService

    # Persist scraped data - pick MongoDB or PostgreSQL
    from company_crawler import get_storage

    storage = get_storage("mongodb", name="companies")  # or get_storage("postgresql", ...)
    storage.connect()
    storage.store_data(company_data)
"""

from typing import Optional

# Re-export craft services for convenient access
from craft import (
    CraftCompanySearchingService,
    CraftCompanyPageScrapingService,
)

# Re-export storage backends for convenient access
from storage.mongo_store import MongoDBStorage
from storage.postgres_store import PostgreSQLStorage, PostgresUpdateResult
from interfaces.iconfig import IDatabaseConfig

__all__ = [
    # Craft services
    "CraftCompanySearchingService",
    "CraftCompanyPageScrapingService",
    # Storage backends
    "MongoDBStorage",
    "PostgreSQLStorage",
    "PostgresUpdateResult",
    "IDatabaseConfig",
    # Service registries
    "AVAILABLE_SOURCES",
    "AVAILABLE_STORAGES",
    "get_search_service",
    "get_scraping_service",
    "get_storage",
]

# Registry of available data sources
AVAILABLE_SOURCES = {
    "craft": {
        "search_service": CraftCompanySearchingService,
        "scraping_service": CraftCompanyPageScrapingService,
    }
}

# Registry of available storage backends. Keys double as the canonical
# IDatabaseConfig.driver values ("mongodb" / "postgresql").
AVAILABLE_STORAGES = {
    "mongodb": MongoDBStorage,
    "postgresql": PostgreSQLStorage,
}


def get_search_service(source: str = "craft", **kwargs):
    """
    Get a company search service for the specified source.

    Args:
        source: Data source name (default: "craft"). Available sources: craft
        **kwargs: Additional arguments passed to the service constructor

    Returns:
        A search service instance for the specified source

    Raises:
        ValueError: If source is not available

    Example:
        >>> from company_crawler import get_search_service
        >>> from interfaces.iconfig import IQuery
        >>> service = get_search_service("craft")
        >>> results = service.search_company(IQuery(company_name="Amazon"))
    """
    if source not in AVAILABLE_SOURCES:
        raise ValueError(
            f"Unknown source: {source}. Available sources: {list(AVAILABLE_SOURCES.keys())}"
        )

    service_class = AVAILABLE_SOURCES[source]["search_service"]
    return service_class(**kwargs)


def get_scraping_service(source: str = "craft", **kwargs):
    """
    Get a company page scraping service for the specified source.

    Args:
        source: Data source name (default: "craft"). Available sources: craft
        **kwargs: Additional arguments passed to the service constructor

    Returns:
        A scraping service instance for the specified source

    Raises:
        ValueError: If source is not available

    Example:
        >>> from company_crawler import get_scraping_service
        >>> from interfaces.iconfig import ICrawlerConfig
        >>> service = get_scraping_service("craft")
        >>> data = service.scrape_company_page(
        ...     "https://craft.co/amazon",
        ...     ICrawlerConfig()
        ... )
    """
    if source not in AVAILABLE_SOURCES:
        raise ValueError(
            f"Unknown source: {source}. Available sources: {list(AVAILABLE_SOURCES.keys())}"
        )

    if "page_parser" not in kwargs:
        from craft.parsers.company_page_parser import CraftParser
        kwargs["page_parser"] = CraftParser()

    service_class = AVAILABLE_SOURCES[source]["scraping_service"]
    return service_class(**kwargs)


def get_storage(
    driver: str = "mongodb",
    config: Optional[IDatabaseConfig] = None,
    **config_kwargs,
):
    """
    Get a storage backend for persisting scraped company data.

    Args:
        driver: Storage backend name. Available drivers: mongodb,
            postgresql (case-insensitive)
        config: Optional pre-built IDatabaseConfig. When omitted, one is
            created from **config_kwargs
        **config_kwargs: Keyword arguments forwarded to IDatabaseConfig
            (e.g. name, host, port, user, password, plus any driver-specific
            extra options)

    Returns:
        A DataStorage instance (MongoDBStorage or PostgreSQLStorage) for the
        requested backend. The connection is not opened yet - call
        .connect() before .store_data(...)

    Raises:
        ValueError: If driver is not available

    Example:
        >>> from company_crawler import get_storage
        >>> storage = get_storage("mongodb", name="companies")
        >>> storage.connect()
        >>> storage.store_data(company_data)
    """
    key = str(driver).lower()
    if key not in AVAILABLE_STORAGES:
        raise ValueError(
            f"Unknown storage driver: {driver}. Available drivers: {sorted(AVAILABLE_STORAGES)}"
        )

    storage_class = AVAILABLE_STORAGES[key]
    if config is None:
        # "driver" is the backend selector parameter, so it can never arrive
        # through **config_kwargs; the key doubles as the canonical driver name.
        config_kwargs["driver"] = key
        config = IDatabaseConfig(**config_kwargs)

    return storage_class(config)
