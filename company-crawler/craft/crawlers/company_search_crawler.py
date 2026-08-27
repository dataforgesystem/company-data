import requests
from base.scraper import CompanyNameScraper
from logger import get_logger
from utils.scraping_utils import ScrapingUtils

logger = get_logger(__name__)


class CompanySearchCrawler(CompanyNameScraper):

    def build_proxies(self, proxy: str):
        if not proxy:
            return None
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def scrape(self, query, config):
        try:
            headers = ScrapingUtils.prepare_search_query_headers()
            payload = ScrapingUtils.prepare_search_query_payload(query)
            URL = ScrapingUtils.get_search_query_url()
            response = requests.post(
                url=URL,
                data=payload,
                headers=headers,
                proxies=self.build_proxies(config.proxy),
            )
            response.raise_for_status()
            return response.json()
        except Exception as ex:
            logger.exception(f"Error while trying to fetch company by name: {ex}")
