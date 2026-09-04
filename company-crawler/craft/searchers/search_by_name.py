from base.searcher import CompanySearcher
from typing import List
from craft.parsers.search_result_parser import SearchResponseParser
from interfaces.search_response import ISearchResponse


class CompanySearchByName(CompanySearcher):

    def search_by_name(self, name, config) -> List[ISearchResponse]:
        response = self.searcher.scrape(name, config)
        return self.search_response_parser.parse(response)

    def search_by_symbol(self, symbol, config):
        raise NotImplementedError("Not implemented!")
