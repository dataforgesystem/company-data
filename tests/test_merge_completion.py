"""Regression tests for lossless collection reconciliation in the LLM merger.

The merge itself is LLM-driven, but completeness is not left to the model:
``LLMProfileMerger`` completes every collection field to the union of all
sources, so a model that omits entries (small local models routinely do on
long lists) can never cause data loss. These tests pin down that behaviour
and the identity rules it relies on. No LLM or database is needed.
"""

from datetime import datetime, timezone

import pytest

from company_data_crawler.models.company_data import (
    CompanyData,
    CompanyEmployeeCount,
    CompanyFundingInfo,
    KeyExecutive,
)
from company_data.database.base import SourcedProfile
from company_data.pipeline.llm_merger import LLMProfileMerger, MergedProfile


class StubLLM:
    """Stands in for the merge LLM, returning a canned reconciliation."""

    def __init__(self, merged: MergedProfile) -> None:
        self.merged = merged
        self.received_prompt: str = ""

    def generate_structured_output(
        self, prompt, response_schema, system_instructions
    ) -> MergedProfile:
        assert response_schema is MergedProfile
        self.received_prompt = prompt
        return self.merged


class ExplodingLLM(StubLLM):
    """Fails the test if the merger ever calls the LLM."""

    def generate_structured_output(self, **kwargs):
        raise AssertionError("The LLM must not be called here")


def source_record(source: str, **fields) -> SourcedProfile:
    """One crawler record, in the shape a store hands to the merger."""
    profile = CompanyData(
        company_name="Acme",
        company_domain="acme.com",
        last_scraped_at=datetime.now(timezone.utc),
        **fields,
    )
    return SourcedProfile(source_name=source, profile=profile)


def merge(records, llm_output: MergedProfile) -> CompanyData:
    """Run the merger with a canned LLM response."""
    return LLMProfileMerger(StubLLM(llm_output)).merge_profiles(records)


def test_every_record_must_be_reconcilable():
    """An empty record set is a caller error, not an empty merge."""
    with pytest.raises(ValueError):
        merge([], MergedProfile())


def test_llm_omissions_are_restored_losslessly():
    """Entries a source provided survive even when the LLM dropped them."""
    record = source_record(
        "craft",
        key_executives=[
            KeyExecutive(name="Ada", title="CEO"),
            KeyExecutive(name="Grace", title="CTO"),
        ],
    )
    merged = merge([record], MergedProfile())

    assert sorted(e.name for e in merged.key_executives) == ["Ada", "Grace"]


def test_partial_llm_entry_matches_full_source_entry():
    """A round echoed without its date must not duplicate the source entry."""
    record = source_record(
        "craft",
        company_funding_info=[
            CompanyFundingInfo(funding_round="Series A", funding_date="Jan 2020")
        ],
    )
    llm_output = MergedProfile(
        company_funding_info=[CompanyFundingInfo(funding_round="Series A")]
    )

    assert len(merge([record], llm_output).company_funding_info) == 1


def test_distinct_entries_survive_the_wildcard_match():
    """Wildcard matching must not swallow genuinely different entries."""
    record = source_record(
        "craft",
        company_funding_info=[
            CompanyFundingInfo(funding_round="Series A", funding_date="Jan 2020"),
            CompanyFundingInfo(funding_round="Series B", funding_date="Jun 2021"),
        ],
    )
    llm_output = MergedProfile(
        company_funding_info=[CompanyFundingInfo(funding_round="Series A")]
    )
    merged = merge([record], llm_output)

    assert sorted(f.funding_round for f in merged.company_funding_info) == [
        "Series A",
        "Series B",
    ]


def test_entries_without_identity_fields_are_never_conflated():
    """Date-less entries have no identity, so they stay distinct data."""
    record = source_record(
        "craft",
        company_employee_counts=[
            CompanyEmployeeCount(total_employees=100),
            CompanyEmployeeCount(total_employees=200),
        ],
    )
    merged = merge([record], MergedProfile())

    assert sorted(e.total_employees for e in merged.company_employee_counts) == [
        100,
        200,
    ]


def test_llm_deduplication_is_respected_case_insensitively():
    """The LLM's own dedup wins: the same person is not added back."""
    newest = source_record(
        "owler", key_executives=[KeyExecutive(name="Ada", title="CEO")]
    )
    older = source_record(
        "craft", key_executives=[KeyExecutive(name="Ada", title="CEO")]
    )
    llm_output = MergedProfile(
        key_executives=[KeyExecutive(name="ADA", title="ceo")]
    )
    merged = merge([newest, older], llm_output)

    assert [e.name for e in merged.key_executives] == ["ADA"]


def test_llm_duplicate_entries_are_collapsed():
    """A model that returns the same person twice must not leak a duplicate."""
    newest = source_record("owler", company_founded_year=2010)
    older = source_record("craft", company_founded_year=2001)
    llm_output = MergedProfile(
        key_executives=[
            KeyExecutive(name="John Collison", title="President"),
            KeyExecutive(name="john collison", title="Co-Founder & President"),
        ]
    )
    merged = merge([newest, older], llm_output)

    assert [e.name for e in merged.key_executives] == ["John Collison"]


def test_the_richest_duplicate_is_the_one_kept():
    """Collapsing duplicates keeps the entry carrying the most detail."""
    newest = source_record("owler", company_founded_year=2010)
    older = source_record("craft", company_founded_year=2001)
    llm_output = MergedProfile(
        key_executives=[
            KeyExecutive(name="Ada", title="CTO"),
            KeyExecutive(
                name="ada",
                title="CTO",
                linkedin_url="https://linkedin.com/in/ada",
            ),
        ]
    )
    merged = merge([newest, older], llm_output)

    assert len(merged.key_executives) == 1
    assert merged.key_executives[0].linkedin_url == "https://linkedin.com/in/ada"


def test_collections_unite_across_sources():
    """Fields supplied by different sources all reach the merged view."""
    newest = source_record(
        "owler", key_executives=[KeyExecutive(name="Grace", title="CTO")]
    )
    older = source_record(
        "craft", key_executives=[KeyExecutive(name="Ada", title="CEO")]
    )
    merged = merge([newest, older], MergedProfile())

    assert sorted(e.name for e in merged.key_executives) == ["Ada", "Grace"]


def test_scalar_decisions_stay_with_the_llm():
    """Scalars come from the LLM overlay, not from the completion pass."""
    newest = source_record("owler", company_founded_year=2001)
    older = source_record("craft", company_founded_year=1990)
    merged = merge([newest, older], MergedProfile(company_founded_year=1999))

    assert merged.company_founded_year == 1999


def test_prompt_carries_provenance_and_literal_json_braces():
    """Each record is labelled, and JSON braces are not format placeholders."""
    records = [
        source_record("owler", company_founded_year=2010),
        source_record("craft", company_founded_year=2011),
    ]
    llm = StubLLM(MergedProfile())
    LLMProfileMerger(llm).merge_profiles(records, focus_query="funding history")

    assert '"source_name": "craft"' in llm.received_prompt
    assert '"source_name": "owler"' in llm.received_prompt
    assert "funding history" in llm.received_prompt


def test_single_source_needs_no_llm_call():
    """A single source needs no reconciliation, so no model call happens."""
    record = source_record(
        "craft", key_executives=[KeyExecutive(name="Ada", title="CEO")]
    )
    merged = LLMProfileMerger(ExplodingLLM(MergedProfile())).merge_profiles([record])

    # Nothing to reconcile, but the record is still completed losslessly.
    assert merged.key_executives[0].name == "Ada"