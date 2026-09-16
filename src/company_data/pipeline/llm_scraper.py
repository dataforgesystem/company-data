from company_data.llm.base import LLMProvider
from company_data.pipeline.interfaces.scraper import ScraperBase
from company_data.tools.scraping_tools import (
    get_company_data_by_name,
    get_company_data_by_symbol,
)


class LLMScraper(ScraperBase):
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def scrape_data(self):
        self.llm.call_with_tools(
            "", [get_company_data_by_name, get_company_data_by_symbol], ""
        )
