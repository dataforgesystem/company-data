import unittest

from craft.scraping_orchestrator import CraftCompanyPageScrapingService
from craft.crawlers.selenium_base_url_crawler import SeleniumBaseUrlScraper
from craft.crawlers.http_url_crawler import HTTPUrlScraper
from craft.parsers.company_page_parser import CraftParser


class CraftUrlScraper(unittest.TestCase):
    def setUp(self):
        self._sb_url_scraper = SeleniumBaseUrlScraper(headless=True)
        self._http_url_scraper = HTTPUrlScraper()

        self.parser = CraftParser()

        self._sb_company_page_scraper = CraftCompanyPageScrapingService(
            self._sb_url_scraper, self.parser
        )

        self._http_company_page_scraper = CraftCompanyPageScrapingService(
            self._http_url_scraper, self.parser
        )

    def test_sb_page_scraping(self):
        config = None
        url = "https://craft.co/google"
        expected_result = {}
        response = self._sb_company_page_scraper.scrape_company_page(url, config)
        self.assertNotEqual(response, None)

    def test_http_page_scraping(self):
        config = None
        url = "https://craft.co/amazon"
        expected_result = {}
        response = self._http_company_page_scraper.scrape_company_page(url, config)
        self.assertIsNotNone(response)
