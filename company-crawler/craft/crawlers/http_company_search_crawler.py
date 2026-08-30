from curl_cffi import requests
from base.scraper import CompanyNameScraper
from logger import get_logger
from craft.utils.scraping_utils import ScrapingUtils
from typing import Optional, Any

logger = get_logger(__name__)


class CompanySearchCrawler(CompanyNameScraper):

    def build_proxies(self, proxy: Optional[str]) -> Any:
        if not proxy:
            return None
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def scrape(self, query, config) -> str:
        try:
            headers = ScrapingUtils.prepare_search_query_headers()
            payload = ScrapingUtils.prepare_search_query_payload(query)
            URL = ScrapingUtils.get_search_query_url()
            proxy: Optional[str] = config.proxy if config else None
            response = requests.request(
                "POST",
                URL,
                headers=headers,
                data=payload,
                impersonate="chrome",
                proxies=self.build_proxies(proxy),
                timeout=config.request_timeout,
            )
            response.raise_for_status()
            return response.text
        except Exception as ex:
            logger.exception(f"Error while trying to fetch company by name: {ex}")
            raise
