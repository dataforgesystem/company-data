from pydantic import BaseModel
from enum import Enum


class SupportedSource(Enum):
    CRAFT = "craft"
    OWLER = "owler"
