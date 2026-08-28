import unittest

from craft.scraping_orchestrator import CraftCompanyPageScrapingService
from craft.crawlers.selenium_base_crawler import SeleniumBaseScraper
from craft.parsers.beautiful_soup_parser import CraftParser


class CraftUrlScraper(unittest.TestCase):
    def setUp(self):
        self.url_scraper = SeleniumBaseScraper(headless=True)
        self.parser = CraftParser()
        self.company_page_scraper = CraftCompanyPageScrapingService(
            self.url_scraper, self.parser
        )

    def test_page_scraping(self):
        config = None
        url = "https://craft.co/google"
        expected_result = {}
        response = self.company_page_scraper.scrape_company_page(url, config)
        self.assertNotEqual(response, None)
