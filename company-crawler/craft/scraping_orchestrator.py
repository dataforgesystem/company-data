import sys
from pathlib import Path

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))

from craft.parsers.company_page_parser import CraftParser
from craft.crawlers.http_url_crawler import HTTPUrlScraper
from craft.crawlers.selenium_base_url_crawler import SeleniumBaseUrlScraper
from craft.crawlers.url_scraper_chain import UrlScraperChain
from base.scraper import UrlScraper
from base.parser import Parser
from interfaces.iconfig import ICrawlerConfig
from logger import get_logger
from typing import Optional
from storage.persistent_disk_cache import DiskCache
from models.company_data import CompanyData
from craft.utils.general_utils import GeneralUtils
import os

logger = get_logger("Craft Scraping Orchestrator")


class CraftCompanyPageScrapingService:
    def __init__(
        self,
        url_scraper: Optional[UrlScraper],
        page_parser: Parser,
    ):
        self.url_scraper = url_scraper or UrlScraperChain(
            (HTTPUrlScraper(), SeleniumBaseUrlScraper())
        )
        self.page_parser = page_parser
        self._disk_cache = DiskCache(CompanyData, os.getcwd())

    def fetch_page(self, url: str, config: ICrawlerConfig) -> str:
        try:
            return self.url_scraper.scrape(url, config)
        except Exception:
            logger.exception("Error while fetching page: %s", url)
            raise

    def parse_page(self, page_data: str):
        try:
            return self.page_parser.parse(page_data)
        except Exception:
            logger.exception("Error while parsing page")
            raise

    def scrape_company_page(self, url: str, config: Optional[ICrawlerConfig] = None):
        crawler_config = config if config is not None else ICrawlerConfig()
        try:
            if not crawler_config.force_rescrape:
                cached_data = self._disk_cache.get(url)
                if cached_data:
                    return cached_data

            page_data = self.fetch_page(url, crawler_config)
            parsed_page = self.page_parser.parse(page_data)
            self._disk_cache.set(
                url,
                parsed_page,
                GeneralUtils.generate_time_from_now(
                    crawler_config.company_cache_expiry_time_days
                ).timestamp(),
            )
            return parsed_page
        except Exception:
            logger.exception("Error while processing page: %s", url)
            raise
