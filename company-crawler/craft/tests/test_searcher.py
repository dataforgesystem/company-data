import unittest


from craft.search_orchestrator import CraftCompanySearchingService
from craft.crawlers.company_search_crawler import CompanySearchCrawler
from searchers.search_by_name import CompanySearchByName
from craft.parsers.search_result_parser import CraftSearchParser
from interfaces.iconfig import IQuery
from interfaces.search_response import ISearchResponse


class CraftSearchTester(unittest.TestCase):
    def setUp(self):
        self.crawler = CompanySearchCrawler()
        self.search_parser = CraftSearchParser()
        self.searcher = CompanySearchByName(self.crawler, self.search_parser)
        self.search_service = CraftCompanySearchingService(self.searcher)

    def test_search_by_name_amazon(self):
        config = None
        query = IQuery(company_name="amazon")
        result = self.search_service.search_company(query, config)
        expected_response = ISearchResponse(
            company_name="Amazon",
            source_url="https://craft.co/amazon",
            logo_url="https://uploads5.craft.co/uploads/company/logo/119xx/11981/normal_c3d4b9d868a5b58c.jpeg",
            slug="amazon",
        )
        self.assertIn(expected_response, result)
