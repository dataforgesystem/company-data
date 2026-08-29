"""
Company Crawler - A comprehensive library for searching and scraping company data from multiple sources.

This module provides unified access to company data services from various sources:
  - craft: Craft.co scraping and searching services
  - (Additional sources can be added as plugins)

Available Services:
  - Search: Find companies by name or stock ticker
  - Scraping: Scrape and parse company pages
  - Exporting: Export data in various formats (CSV, JSON, Parquet)

Quick Start:
    # Using Craft source (default)
    from company_crawler.craft import create_search_service, create_scraping_service
    
    search_service = create_search_service()
    scraping_service = create_scraping_service()
    
    # Or access services through source-specific imports
    from company_crawler.craft import CraftCompanySearchingService, CraftCompanyPageScrapingService
"""

# Re-export craft services for convenient access
from craft import (
    CraftCompanySearchingService,
    CraftCompanyPageScrapingService,
)

__all__ = [
    # Craft services
    "CraftCompanySearchingService",
    "CraftCompanyPageScrapingService",
    # Service registry
    "AVAILABLE_SOURCES",
    "get_search_service",
    "get_scraping_service",
]

# Registry of available data sources
AVAILABLE_SOURCES = {
    "craft": {
        "search_service": CraftCompanySearchingService,
        "scraping_service": CraftCompanyPageScrapingService,
    }
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
        from craft.parsers.beautiful_soup_parser import CraftParser
        kwargs["page_parser"] = CraftParser()

    service_class = AVAILABLE_SOURCES[source]["scraping_service"]
    return service_class(**kwargs)
