from base.searcher import CompanySearcher


class CompanySearchByname(CompanySearcher):

    def search_by_name(self, name, config):
        return self.searcher.scrape(name, config)

    def search_by_symbol(self, symbol, config):
        raise NotImplementedError("Not implemented!")
