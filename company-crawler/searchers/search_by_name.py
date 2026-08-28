from base.searcher import CompanySearcher
from typing import List
from craft.parsers.search_result_parser import SearchResponseParser


class CompanySearchByName(CompanySearcher):

    def search_by_name(self, name, config) -> List[str]:
        response = self.searcher.scrape(name, config)
        return self.search_response_parser.parse(response)

    def search_by_symbol(self, symbol, config):
        raise NotImplementedError("Not implemented!")
