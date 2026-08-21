from abc import ABC, abstractmethod
from models import CompanyData


class Parser(ABC):
    @abstractmethod
    def parse(self, data: str) -> CompanyData:
        pass
