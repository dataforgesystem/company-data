from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, model_validator

from company_data.llm.base import ILLMProvider


class ExtractedData(BaseModel):
    """Company names plus intent parsed from one user query.

    ``company_names`` holds every company the query mentions (e.g.
    ``"Compare Stripe and Adyen"`` yields ``["Stripe", "Adyen"]``).
    ``company_name`` is kept as a convenience alias for the first entry so
    existing single-company call sites keep working unchanged.
    """

    company_names: list[str] = Field(
        default_factory=list,
        description="Company names extracted from the user query, in mention order",
    )
    company_name: str = Field(
        default="",
        description="(Legacy alias for company_names[0]) "
        "Company name extracted from the user query",
    )
    intent: str = Field(
        default="", min_length=3, description="What is the intent of the user query?"
    )
    is_valid: bool = Field(
        default=False,
        description="Whether the extracted intent is valid",
    )

    @model_validator(mode="after")
    def _sync_company_name_alias(self) -> "ExtractedData":
        """Keeps ``company_name`` and ``company_names`` consistent either way."""
        names = [name.strip() for name in (self.company_names or []) if name.strip()]
        first = (self.company_name or "").strip()
        if names and not first:
            self.company_name = names[0]
        elif first and not names:
            self.company_names = [first]
        elif names and first and names[0] != first:
            self.company_names = [first, *[name for name in names if name != first]]
            self.company_name = first
        else:
            self.company_names = names
            self.company_name = first
        return self


class BaseExtractor(ABC):
    def __init__(self, llm: ILLMProvider) -> None:
        self.llm = llm
        super().__init__()

    @abstractmethod
    def extract_intent(self, text_query: str) -> ExtractedData:
        """Extract out the intents of the text"""
