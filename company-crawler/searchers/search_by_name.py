from base.searcher import Searcher


class CompanySearchByname(Searcher):

    def search_by_name(self, name, config):
        return self.searcher.scrape(name, config)

    def search_by_symbol(self, symbol, config):
        raise NotImplementedError("Not implemented!")
