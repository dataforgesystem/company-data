"""
Craft Crawler - Company data scraping and searching orchestrator for Craft.co

Exposed services:
  - CraftCompanySearchingService: Search for companies by name or stock ticker
  - CraftCompanyPageScrapingService: Scrape and parse company pages
  - create_search_service(): Factory function for search service
  - create_scraping_service(): Factory function for scraping service

Example:
    from craft import create_search_service, create_scraping_service
    from interfaces.iconfig import IQuery, ICrawlerConfig

    search_service = create_search_service()
    results = search_service.search_company(IQuery(company_name="Amazon"))

    scraping_service = create_scraping_service()
    data = scraping_service.scrape_company_page("https://craft.co/amazon")
"""

from craft.scraping_orchestrator import CraftCompanyPageScrapingService
from craft.search_orchestrator import CraftCompanySearchingService
from craft.parsers.company_page_parser import CraftParser

__all__ = [
    "CraftCompanySearchingService",
    "CraftCompanyPageScrapingService",
    "create_search_service",
    "create_scraping_service",
]


def create_search_service(searcher=None) -> CraftCompanySearchingService:
    """
    Create a Craft company search service.

    Args:
        searcher: Optional custom searcher implementation. If None, uses default.

    Returns:
        CraftCompanySearchingService instance ready to search for companies.

    Example:
        >>> from craft import create_search_service
        >>> from interfaces.iconfig import IQuery
        >>> service = create_search_service()
        >>> results = service.search_company(IQuery(company_name="Amazon"))
    """
    return CraftCompanySearchingService(searcher)


def create_scraping_service(
    url_scraper=None, page_parser=None
) -> CraftCompanyPageScrapingService:
    """
    Create a Craft company page scraping service.

    Args:
        url_scraper: Optional custom URL scraper. If None, uses default chain.
        page_parser: Optional custom page parser. If None, uses CraftParser.

    Returns:
        CraftCompanyPageScrapingService instance ready to scrape pages.

    Example:
        >>> from craft import create_scraping_service
        >>> from interfaces.iconfig import ICrawlerConfig
        >>> service = create_scraping_service()
        >>> data = service.scrape_company_page("https://craft.co/amazon")
    """
    if page_parser is None:
        page_parser = CraftParser()

    return CraftCompanyPageScrapingService(url_scraper, page_parser)
