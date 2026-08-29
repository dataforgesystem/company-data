import unittest
from unittest.mock import Mock


from craft.search_orchestrator import CraftCompanySearchingService
from craft.crawlers.http_company_search_crawler import CompanySearchCrawler
from craft.crawlers.selenium_base_search_crawler import SeleniumbaseSearchCrawler
from craft.searchers.search_by_name import CompanySearchByName
from craft.parsers.search_result_parser import CraftSearchParser
from interfaces.iconfig import IQuery
from interfaces.search_response import ISearchResponse


class CraftSearchTester(unittest.TestCase):
    def setUp(self):
        self.http_crawler = CompanySearchCrawler()  # search using HTTP strategy
        self.selenium_base_crawler = SeleniumbaseSearchCrawler(
            headless=False
        )  # search using SB strategy

        self.search_parser = CraftSearchParser()  # works with both the strategy

        self.http_searcher = CompanySearchByName(self.http_crawler, self.search_parser)
        self.http_search_service = CraftCompanySearchingService(self.http_searcher)

        self.sb_searcher = CompanySearchByName(
            self.selenium_base_crawler, self.search_parser
        )
        self.sb_search_service = CraftCompanySearchingService(self.sb_searcher)

    def test_http_search_by_name_amazon(self):
        config = None
        query = IQuery(company_name="amazon")
        result = self.http_search_service.search_company(query, config)
        expected_response = ISearchResponse(
            company_name="Amazon",
            source_url="https://craft.co/amazon",
            logo_url="https://uploads5.craft.co/uploads/company/logo/119xx/11981/normal_c3d4b9d868a5b58c.jpeg",
            slug="amazon",
        )
        self.assertIn(expected_response, result)

    def test_sb_search_by_name_amazon(self):
        config = None
        query = IQuery(company_name="amazon")
        result = self.sb_search_service.search_company(query, config)
        expected_response = ISearchResponse(
            company_name="Amazon",
            source_url="https://craft.co/amazon",
            logo_url="https://uploads5.craft.co/uploads/company/logo/119xx/11981/normal_c3d4b9d868a5b58c.jpeg",
            slug="amazon",
        )
        self.assertIn(expected_response, result)

    def test_search_by_name_with_no_matches_returns_empty_list(self):
        crawler = Mock()
        crawler.scrape.return_value = '{"data": {"universalSearch": []}}'
        search_service = CraftCompanySearchingService(
            CompanySearchByName(crawler, self.search_parser)
        )

        result = search_service.search_company(IQuery(company_name="unknown"))

        self.assertEqual(result, [])

    def test_search_failure_is_propagated(self):
        crawler = Mock()
        crawler.scrape.side_effect = TimeoutError("GraphQL response not found")
        search_service = CraftCompanySearchingService(
            CompanySearchByName(crawler, self.search_parser)
        )

        with self.assertRaises(TimeoutError):
            search_service.search_company(IQuery(company_name="amazon"))

    def test_graphql_errors_are_propagated(self):
        crawler = Mock()
        crawler.scrape.return_value = (
            '{"errors": [{"message": "upstream failure"}], "data": null}'
        )
        search_service = CraftCompanySearchingService(
            CompanySearchByName(crawler, self.search_parser)
        )

        with self.assertRaises(ValueError):
            search_service.search_company(IQuery(company_name="amazon"))

    def test_http_crawler_failure_is_propagated(self):
        crawler = CompanySearchCrawler()
        crawler.build_proxies = Mock(side_effect=ConnectionError("network down"))

        with self.assertRaises(ConnectionError):
            crawler.scrape("amazon", None)
