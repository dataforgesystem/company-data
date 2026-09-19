from typing import TypedDict

from company_data_crawler.models.company_data import CompanyData

from company_data.database.base import SourcedProfile
from company_data.pipeline.interfaces.extractor import ExtractedData


class AgentState(TypedDict, total=False):
    """Shared state flowing through the company research graph.

    All keys are optional: nodes return partial updates that LangGraph
    merges into the running state.

    Multi-company queries resolve one profile per company: ``company_domains``
    pairs each requested name with its domain, ``company_source_profiles``
    holds the per-company per-source records in the same order, and
    ``company_profiles`` holds one merged/resolved profile per company.
    ``source_profiles`` is a flattened view of every requested company's
    records (observability), while ``company_domain``/``merged_profile``
    mirror the first company for backward compatibility with single-company
    consumers.
    """

    query: str
    extracted: ExtractedData | None
    company_names: list[str]
    company_domains: list[str | None]
    company_profiles: list[CompanyData | None]
    company_source_profiles: list[list[SourcedProfile]]
    company_domain: str | None
    source_profiles: list[SourcedProfile]
    merged_profile: CompanyData | None
    answer: str
    cache_hit: bool

