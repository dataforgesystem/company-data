import sys
from pathlib import Path

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))

from logger import get_logger
from craft.crawlers.company_name_scraper_chain import CompanyNameScraperChain
from craft.crawlers.http_company_search_crawler import CompanySearchCrawler
from craft.crawlers.selenium_base_search_crawler import SeleniumbaseSearchCrawler
from craft.parsers.search_result_parser import CraftSearchParser
from searchers.search_by_name import CompanySearchByName
from base.searcher import CompanySearcher
from interfaces.iconfig import ICrawlerConfig, IQuery
from interfaces.search_response import ISearchResponse
from typing import List

logger = get_logger("Craft Search Orchestrator")


class CraftCompanySearchingService:
    def __init__(self, searcher: CompanySearcher | None = None):
        self.searcher = searcher or CompanySearchByName(
            CompanyNameScraperChain(
                (CompanySearchCrawler(), SeleniumbaseSearchCrawler())
            ),
            CraftSearchParser(),
        )

    def search_company(
        self, query: IQuery, config: ICrawlerConfig | None = None
    ) -> List[ISearchResponse]:
        crawler_config = config or ICrawlerConfig()
        results: list[str] = []

        try:
            if query.company_name:
                result = self.searcher.search_by_name(
                    query.company_name, crawler_config
                )
                if result:
                    results.extend(result)
            if query.stock_ticket:
                result = self.searcher.search_by_symbol(
                    query.stock_ticket, crawler_config
                )
                if result:
                    results.extend(result)
            return results
        except Exception:
            logger.exception("Error while searching for company: %s", query)
            raise
