import unittest
from pathlib import Path
from unittest.mock import Mock

from craft.crawlers.url_scraper_chain import UrlScraperChain
from craft.crawlers.http_url_crawler import HTTPUrlScraper
from craft.crawlers.selenium_base_url_crawler import SeleniumBaseUrlScraper
from craft.scraping_orchestrator import CraftCompanyPageScrapingService
from bs4 import BeautifulSoup
from interfaces.iconfig import ICrawlerConfig


class UrlScraperChainTest(unittest.TestCase):
    def setUp(self):
        self.config = ICrawlerConfig()

    def test_returns_http_result_without_calling_selenium(self):
        http_scraper = Mock()
        http_scraper.scrape.return_value = "http result"
        selenium_scraper = Mock()

        result = UrlScraperChain((http_scraper, selenium_scraper)).scrape(
            "https://example.test", self.config
        )

        self.assertEqual(result, "http result")
        http_scraper.scrape.assert_called_once()
        selenium_scraper.scrape.assert_not_called()

    def test_falls_back_to_selenium_when_http_fails(self):
        http_scraper = Mock()
        http_scraper.scrape.side_effect = ConnectionError("HTTP unavailable")
        selenium_scraper = Mock()
        selenium_scraper.scrape.return_value = "selenium result"

        result = UrlScraperChain((http_scraper, selenium_scraper)).scrape(
            "https://example.test", self.config
        )

        self.assertEqual(result, "selenium result")
        http_scraper.scrape.assert_called_once()
        selenium_scraper.scrape.assert_called_once()

    def test_raises_last_error_when_all_scrapers_fail(self):
        http_scraper = Mock()
        http_scraper.scrape.side_effect = ConnectionError("HTTP unavailable")
        selenium_scraper = Mock()
        selenium_scraper.scrape.side_effect = TimeoutError("Selenium timed out")

        with self.assertRaisesRegex(TimeoutError, "Selenium timed out"):
            UrlScraperChain((http_scraper, selenium_scraper)).scrape(
                "https://example.test", self.config
            )

    def test_requires_at_least_one_scraper(self):
        with self.assertRaises(ValueError):
            UrlScraperChain(())

    def test_orchestrator_uses_http_then_selenium_by_default(self):
        service = CraftCompanyPageScrapingService(None, Mock())

        self.assertIsInstance(service.url_scraper, UrlScraperChain)
        self.assertIsInstance(service.url_scraper.scrapers[0], HTTPUrlScraper)
        self.assertIsInstance(service.url_scraper.scrapers[1], SeleniumBaseUrlScraper)

    def test_http_extractor_reads_saved_window_app_response(self):
        response_path = Path(__file__).parents[1] / "response.html"
        with response_path.open(encoding="utf-8") as response_file:
            soup = BeautifulSoup(response_file.read(), "html.parser")

        cache = HTTPUrlScraper()._extract_cache_from_scripts(soup)

        self.assertIsInstance(cache, dict)
        self.assertIn("ROOT_QUERY", cache)


if __name__ == "__main__":
    unittest.main()
