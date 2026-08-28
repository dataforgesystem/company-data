import unittest
from unittest.mock import Mock

from craft.crawlers.company_name_scraper_chain import CompanyNameScraperChain
from craft.crawlers.http_company_search_crawler import CompanySearchCrawler
from craft.crawlers.selenium_base_search_crawler import SeleniumbaseSearchCrawler
from craft.search_orchestrator import CraftCompanySearchingService
from interfaces.iconfig import ICrawlerConfig


class CompanyNameScraperChainTest(unittest.TestCase):
    def setUp(self):
        self.config = ICrawlerConfig()

    def test_returns_http_result_without_calling_selenium(self):
        http_scraper = Mock()
        http_scraper.scrape.return_value = "http result"
        selenium_scraper = Mock()

        result = CompanyNameScraperChain((http_scraper, selenium_scraper)).scrape(
            "amazon", self.config
        )

        self.assertEqual(result, "http result")
        http_scraper.scrape.assert_called_once()
        selenium_scraper.scrape.assert_not_called()

    def test_falls_back_to_selenium_when_http_fails(self):
        http_scraper = Mock()
        http_scraper.scrape.side_effect = ConnectionError("HTTP unavailable")
        selenium_scraper = Mock()
        selenium_scraper.scrape.return_value = "selenium result"

        result = CompanyNameScraperChain((http_scraper, selenium_scraper)).scrape(
            "amazon", self.config
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
            CompanyNameScraperChain((http_scraper, selenium_scraper)).scrape(
                "amazon", self.config
            )

    def test_requires_at_least_one_scraper(self):
        with self.assertRaises(ValueError):
            CompanyNameScraperChain(())

    def test_orchestrator_uses_http_then_selenium_by_default(self):
        service = CraftCompanySearchingService()
        chain = service.searcher.searcher

        self.assertIsInstance(chain, CompanyNameScraperChain)
        self.assertIsInstance(chain.scrapers[0], CompanySearchCrawler)
        self.assertIsInstance(chain.scrapers[1], SeleniumbaseSearchCrawler)


if __name__ == "__main__":
    unittest.main()
