import sys
from pathlib import Path

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))

from parsers.beautiful_soup_parser import CraftParser
from crawlers.selenium_base_crawler import SeleniumBaseScraper
from base.scraper import Scraper
from base.parser import Parser
from logger import get_logger

logger = get_logger("Craft Orchestrator")


class Orchestrator:
    def __init__(self, scraper: Scraper, parser: Parser):
        self.scraper = scraper
        self.parser = parser

    def get_page(self, url: str):
        try:
            return self.scraper.scrape(url)
        except Exception as ex:
            logger.exception(f"Error at get_page: {ex}")

    def parse_page(self, page_data: str):
        try:
            return self.parser.parse(page_data)
        except Exception as ex:
            logger.exception(f"Error at parse_page: {ex}")

    def start(self, url: str):
        try:
            page_data = self.get_page(url)
            parsed_data = self.parse_page(page_data)
            # return parsed_data
        except Exception as ex:
            logger.exception(f"Error at start: {ex}")


if __name__ == "__main__":
    parser = CraftParser()
    scraper = SeleniumBaseScraper()
    orchestrator = Orchestrator(scraper, parser)
    data = orchestrator.start("https://craft.co/amazon")
    print(data)
