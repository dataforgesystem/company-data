from collections.abc import Iterable

from base.scraper import CompanyNameScraper
from interfaces.iconfig import ICrawlerConfig
from logger import get_logger

logger = get_logger("Company name scraper chain")


class CompanyNameScraperChain(CompanyNameScraper):
    """Try company-name scrapers in order until one returns a response."""

    def __init__(self, scrapers: Iterable[CompanyNameScraper]):
        self.scrapers = tuple(scrapers)
        if not self.scrapers:
            raise ValueError("CompanyNameScraperChain requires at least one scraper")

    def scrape(self, query: str, config: ICrawlerConfig) -> str:
        last_error: Exception | None = None

        for scraper in self.scrapers:
            try:
                logger.info("Trying %s for %s", type(scraper).__name__, query)
                return scraper.scrape(query, config)
            except Exception as ex:
                last_error = ex
                logger.warning(
                    "%s failed for %s; trying the next scraper",
                    type(scraper).__name__,
                    query,
                    exc_info=True,
                )

        assert last_error is not None
        raise last_error
