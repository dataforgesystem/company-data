from typing import TypedDict

from company_data_crawler.models.company_data import CompanyData

from company_data.database.base import SourcedProfile
from company_data.pipeline.interfaces.extractor import ExtractedData


class AgentState(TypedDict, total=False):
    """Shared state flowing through the company research graph.

    All keys are optional: nodes return partial updates that LangGraph
    merges into the running state.
    """

    query: str
    extracted: ExtractedData | None
    company_domain: str | None
    source_profiles: list[SourcedProfile]
    merged_profile: CompanyData | None
    answer: str
    cache_hit: bool

