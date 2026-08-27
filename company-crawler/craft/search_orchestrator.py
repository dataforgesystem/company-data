import sys
from pathlib import Path

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))

from logger import get_logger
from base.searcher import CompanySearcher
from interfaces.iconfig import ICrawlerConfig, IQuery

logger = get_logger("Craft Search Orchestrator")


class CraftCompanySearchingService:
    def __init__(self, searcher: CompanySearcher):
        self.searcher = searcher

    def search_company(
        self, query: IQuery, config: ICrawlerConfig | None = None
    ) -> list[str]:
        crawler_config = config or ICrawlerConfig()
        results: list[str] = []

        try:
            if query.company_name:
                results.extend(
                    self.searcher.search_by_name(query.company_name, crawler_config)
                )
            if query.stock_ticket:
                results.extend(
                    self.searcher.search_by_symbol(query.stock_ticket, crawler_config)
                )
            return results
        except Exception:
            logger.exception("Error while searching for company: %s", query)
            raise
