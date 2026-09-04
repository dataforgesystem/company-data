from abc import ABC, abstractmethod
from typing import List
from base.scraper import CompanyNameScraper
from interfaces.iconfig import ICrawlerConfig
from interfaces.search_response import ISearchResponse
from base.search_parser import SearchResponseParser


class CompanySearcher(ABC):
    def __init__(
        self, searcher: CompanyNameScraper, search_response_parser: SearchResponseParser
    ):
        self.searcher = searcher
        self.search_response_parser = search_response_parser

    @abstractmethod
    def search_by_name(
        self, name: str, config: ICrawlerConfig
    ) -> List[ISearchResponse]:
        pass

    @abstractmethod
    def search_by_symbol(
        self, symbol: str, config: ICrawlerConfig
    ) -> List[ISearchResponse]:
        pass
