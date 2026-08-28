from abc import ABC, abstractmethod
from models.company_data import CompanyData


class DataExporter(ABC):

    @abstractmethod
    def export_data(self, data: CompanyData, filepath: str = None):
        pass
