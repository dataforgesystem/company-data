from abc import ABC, abstractmethod
from models.company_data import CompanyData
from interfaces.iconfig import ICrawlerConfig
from typing import TypeVar, Generic, Optional, Type
from pydantic import BaseModel
import os

T = TypeVar("T", bound=BaseModel)


class PersistentCache(Generic[T]):
    def __init__(self, model_class: Type[T], base_dir: str) -> None:
        self._model_class = model_class
        self.base_dir = base_dir
        self.folder_path = os.path.join(self.base_dir, self._model_class.__name__)
        super().__init__()

    @abstractmethod
    def set(self, key: str, data: T, expiry_time: float) -> None:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def clear(self):
        pass
