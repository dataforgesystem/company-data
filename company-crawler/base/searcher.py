from abc import ABC, abstractmethod
from typing import List
from base.scraper import CompanyNameScraper
from interfaces.iconfig import ICrawlerConfig


class CompanySearcher(ABC):
    def __init__(self, searcher: CompanyNameScraper):
        self.searcher = searcher

    @abstractmethod
    def search_by_name(self, name: str, config: ICrawlerConfig) -> List[str]:
        pass

    @abstractmethod
    def search_by_symbol(self, symbol: str, config: ICrawlerConfig) -> List[str]:
        pass
