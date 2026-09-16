from abc import ABC, abstractmethod


class ScraperBase(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def scrape_data(self):
        pass
