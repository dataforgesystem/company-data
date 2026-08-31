from typing import Any, Optional, Union, List

from base.persistent_cache import PersistentCache
import diskcache

from interfaces.iconfig import ICrawlerConfig
from interfaces.search_response import ISearchResponse
from models.company_data import CompanyData
from craft.utils.general_utils import GeneralUtils


from typing import Any, Optional, Union, List, TypeVar, Type

from base.persistent_cache import PersistentCache
import diskcache

from interfaces.iconfig import ICrawlerConfig
from interfaces.search_response import ISearchResponse
from models.company_data import CompanyData
from craft.utils.general_utils import GeneralUtils
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class DiskCache(PersistentCache):
    def __init__(self, model_class: Type[T], base_dir: str) -> None:
        super().__init__(model_class, base_dir)
        self._cache = diskcache.Cache(self.folder_path)

    def set(
        self,
        key: str,
        data: Union[T, List[T]],
        expiry_time: float,
    ) -> None:
        # 1. Early exit if data is empty, None, or an empty list safely
        if data is None or (isinstance(data, list) and not data):
            return

        # 2. Track whether the input data is a list
        is_list = isinstance(data, list)
        items_to_validate = data if is_list else [data]

        # 3. Fast, single-pass type validation for all items
        for item in items_to_validate:
            if not isinstance(item, self._model_class):
                raise TypeError(
                    f"Expected {self._model_class.__name__}, got {type(item).__name__}"
                )

        # 4. Serialize while perfectly preserving the shape (Single dict vs List of dicts)
        if is_list:
            serialized_data = [item.model_dump() for item in data]
        else:
            serialized_data = data.model_dump()

        # 5. Persist the clean serialized structure
        self._cache.set(key, serialized_data, expire=expiry_time)

    def get(self, key: str) -> Optional[Union[T, List[T]]]:
        raw_data = self._cache.get(key)
        if raw_data is None:
            return None

        # If disk has a list, it maps back to a flat list of Pydantic models
        if isinstance(raw_data, list):
            return [self._model_class.model_validate(item) for item in raw_data]

        # If disk has a single dict, it maps back to one Pydantic model
        return self._model_class.model_validate(raw_data)

    def delete(self, key: str) -> None:
        """Remove a single key from this specific cache folder."""
        self._cache.delete(key)

    def clear(self) -> None:
        """Wipe ONLY this specific model's data without affecting other files."""
        self._cache.clear()
