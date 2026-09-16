from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from company_data.llm.base import LLMProvider


class ExtractedData(BaseModel):
    company_name: str = Field(
        default="",
        description="Company name extracted from the user query",
        min_length=3,
    )
    intent: str = Field(
        default="", min_length=3, description="What is the intent of the user query?"
    )
    is_valid: bool = Field(
        default=False,
        description="Whether the extracted intent is valid",
    )


class BaseExtractor(ABC):
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm
        super().__init__()

    @abstractmethod
    def extract_intent(self, text_query: str) -> ExtractedData:
        """Extract out the intents of the text"""
