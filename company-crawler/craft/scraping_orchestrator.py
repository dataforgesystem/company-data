import sys
from pathlib import Path

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))

from parsers.beautiful_soup_parser import CraftParser
from crawlers.selenium_base_crawler import SeleniumBaseScraper
from base.scraper import UrlScraper
from base.parser import Parser
from interfaces.iconfig import ICrawlerConfig
from logger import get_logger

logger = get_logger("Craft Scraping Orchestrator")


class Orchestrator:
    def __init__(self, scraper: UrlScraper, parser: Parser):
        self.scraper = scraper
        self.parser = parser

    def get_page(self, url: str, config: ICrawlerConfig) -> str:
        try:
            return self.scraper.scrape(url, config)
        except Exception:
            logger.exception("Error at get_page: %s", url)
            raise

    def parse_page(self, page_data: str):
        try:
            return self.parser.parse(page_data)
        except Exception:
            logger.exception("Error at parse_page")
            raise

    def start(self, url: str, config: ICrawlerConfig | None = None):
        crawler_config = config or ICrawlerConfig()
        try:
            page_data = self.get_page(url, crawler_config)
            return self.parse_page(page_data)
        except Exception:
            logger.exception("Error at start: %s", url)
            raise


if __name__ == "__main__":
    parser = CraftParser()
    scraper = SeleniumBaseScraper()
    orchestrator = Orchestrator(scraper, parser)
    data = orchestrator.start("https://craft.co/amazon", ICrawlerConfig())
    print(data)
