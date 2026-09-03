from abc import abstractmethod, ABC
from models.company_data import CompanyData


class DataStorage(ABC):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def store_data(self, company_data: CompanyData):
        pass
