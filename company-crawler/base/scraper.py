from abc import ABC, abstractmethod
from interfaces.iconfig import ICrawlerConfig
from typing import Dict


class UrlScraper(ABC):
    @abstractmethod
    def build_proxies(self, proxy: str) -> Dict | str:
        pass

    @abstractmethod
    def scrape(self, url: str, config: ICrawlerConfig) -> str:
        pass


class CompanyNameScraper(ABC):
    @abstractmethod
    def scrape(self, query: str, config: ICrawlerConfig):
        pass
