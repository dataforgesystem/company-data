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
from craft.searchers.search_by_name import CompanySearchByName
from craft.utils.general_utils import GeneralUtils
from base.searcher import CompanySearcher
from interfaces.iconfig import ICrawlerConfig, IQuery
from interfaces.search_response import ISearchResponse
from typing import List, Optional
from storage.persistent_disk_cache import DiskCache
import os

logger = get_logger("Craft Search Orchestrator")


class CraftCompanySearchingService:
    def __init__(self, searcher: Optional[CompanySearcher] = None):
        self.searcher = searcher or CompanySearchByName(
            CompanyNameScraperChain(
                (CompanySearchCrawler(), SeleniumbaseSearchCrawler())
            ),
            CraftSearchParser(),
        )
        self._disk_cache = DiskCache(
            ISearchResponse, os.getcwd()
        )  # intentionally kept away from user control

    def search_company(
        self, query: IQuery, config: Optional[ICrawlerConfig] = None
    ) -> List[ISearchResponse]:
        crawler_config = config or ICrawlerConfig()
        results: list[ISearchResponse] = []

        try:
            if query.company_name:
                if not crawler_config.force_rescrape:
                    result = self._disk_cache.get(
                        query.company_name,
                    )
                    if result:
                        return result

                result = self.searcher.search_by_name(
                    query.company_name, crawler_config
                )
                self._disk_cache.set(
                    query.company_name,
                    result,
                    GeneralUtils.generate_time_from_now(
                        crawler_config.search_cache_expiry_time_days
                    ).timestamp(),
                )
                if result:
                    results.extend(result)
            return results
        except Exception:
            logger.exception("Error while searching for company: %s", query)
            raise
