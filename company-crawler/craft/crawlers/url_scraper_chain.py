from collections.abc import Iterable

from base.scraper import UrlScraper
from interfaces.iconfig import ICrawlerConfig
from logger import get_logger

logger = get_logger("URL scraper chain")


class UrlScraperChain(UrlScraper):
    """Try URL scrapers in order until one returns a page."""

    def __init__(self, scrapers: Iterable[UrlScraper]):
        self.scrapers = tuple(scrapers)
        if not self.scrapers:
            raise ValueError("UrlScraperChain requires at least one scraper")

    def build_proxies(self, proxy: str):
        return None

    def scrape(self, url: str, config: ICrawlerConfig) -> str:
        last_error: Exception | None = None

        for scraper in self.scrapers:
            try:
                logger.info("Trying %s for %s", type(scraper).__name__, url)
                return scraper.scrape(url, config)
            except Exception as ex:
                last_error = ex
                logger.warning(
                    "%s failed for %s; trying the next scraper",
                    type(scraper).__name__,
                    url,
                    exc_info=True,
                )

        assert last_error is not None
        raise last_error
