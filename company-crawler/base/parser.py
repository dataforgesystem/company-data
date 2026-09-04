from abc import ABC, abstractmethod
from models.company_data import CompanyData, CompanyStatus


class Parser(ABC):
    @abstractmethod
    def parse(self, data: str) -> CompanyData | None:
        pass
