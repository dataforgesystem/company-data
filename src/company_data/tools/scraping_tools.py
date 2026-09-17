from company_data_crawler import CompanyDataCrawler
from company_data_crawler.interfaces.iconfig import ICrawlerConfig
from langchain_core.tools import tool

from company_data.config.crawler_configs import CrawlerConfig
from company_data.tools.interfaces.tools_interface import SupportedSource


@tool
def get_company_data_by_name(name: str, source: SupportedSource):
    """Search a company by name, then scrape the first matching page.

    Convenience wrapper combining :meth:`search_company` and
    :meth:`get_company_data`. Only the top-ranked search hit is scraped;
    use the two calls separately when you need to choose among hits.

    Args:
        name: Free-text company name, e.g. ``"airbnb"``.
        source: Registered source key.
        config: Per-call crawl settings. Falls back to the facade-level
            config when omitted.

    Returns:
        The parsed :class:`CompanyData` for the first hit, or ``None``
        when search returned nothing or the page could not be parsed.

    Raises:
        ValueError: If ``source`` is not registered.
    """
    crawler = CompanyDataCrawler(cache_dir=CrawlerConfig.CACHE_DIR)
    config = ICrawlerConfig(proxy=None)
    return crawler.get_company_data_by_name(name, source.value, config=config)


@tool
def get_company_data_by_symbol(symbol: str, source: SupportedSource):
    """Resolve a ticker to a company name, then scrape the first search hit.

    Convenience wrapper combining :meth:`search_company_by_symbol` and
    :meth:`get_company_data`. Only the top-ranked search hit is scraped;
    use the two calls separately when you need to choose among hits.

    Args:
        symbol: Exchange ticker, e.g. ``"MSFT"``.
        source: Registered source key.
        config: Per-call crawl settings. Falls back to the facade-level
            config when omitted.

    Returns:
        The parsed :class:`CompanyData` for the first hit, or ``None``
        when the ticker could not be resolved, search returned nothing,
        or the page could not be parsed.

    Raises:
        ValueError: If ``source`` is not registered, or the ticker symbol
            is empty or cannot be resolved.
    """
    crawler = CompanyDataCrawler(cache_dir=CrawlerConfig.CACHE_DIR)
    config = ICrawlerConfig(proxy=None)
    return crawler.get_company_data_by_symbol(symbol, source.value, config)
