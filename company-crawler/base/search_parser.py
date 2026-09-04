from abc import ABC, abstractmethod
from interfaces.search_response import ISearchResponse
from typing import Dict, Any, List


class SearchResponseParser(ABC):
    @abstractmethod
    def parse(self, data: Dict[Any]) -> List[ISearchResponse]:
        pass
