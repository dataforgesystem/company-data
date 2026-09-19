"""Regression tests for optional merging and multi-company extraction.

Covers the two behaviours these features promise:

- merging is optional: ``off``/``preferred``/``union`` resolve without any
  model call, and the preferred source wins;
- intent extraction supports several companies: ``ExtractedData`` keeps the
  legacy ``company_name`` alias in sync with the new ``company_names`` list.

Tests pass ``preferred_source`` explicitly because the developer's own
``.env`` may set ``MERGE_PREFERRED_SOURCE`` (e.g. to ``owler``); the default
is only asserted where the config itself is the subject.
"""

from datetime import datetime, timezone

import pytest

from company_data_crawler.models.company_data import (
    CompanyData,
    CompanyFundingInfo,
    KeyExecutive,
)

from company_data.config.crawler_configs import MergeConfig
from company_data.database.base import SourcedProfile
from company_data.pipeline.deterministic_merger import (
    DeterministicUnionMerger,
    PreferredSourceMerger,
    build_merger,
)
from company_data.pipeline.interfaces.extractor import ExtractedData


def record(source: str, scraped: datetime, **fields) -> SourcedProfile:
    profile = CompanyData(
        company_name=fields.pop("name", "Acme"),
        company_domain="acme.com",
        last_scraped_at=scraped,
        **fields,
    )
    return SourcedProfile(source_name=source, profile=profile)


OLD = datetime(2024, 1, 1, tzinfo=timezone.utc)
NEW = datetime(2025, 6, 1, tzinfo=timezone.utc)


def craft_and_owler() -> list[SourcedProfile]:
    return [
        record(
            "owler",
            NEW,
            name="Acme, Inc.",
            company_founded_year=2010,
            key_executives=[KeyExecutive(name="Grace", title="CTO")],
        ),
        record(
            "craft",
            OLD,
            name="Acme",
            key_executives=[KeyExecutive(name="Ada", title="CEO")],
        ),
    ]


def test_off_strategy_ignores_freshness():
    """``off`` always returns the preferred source, even when it is older."""
    merged = PreferredSourceMerger("craft").merge_profiles(craft_and_owler())
    assert merged.company_name == "Acme"
    assert [e.name for e in merged.key_executives] == ["Ada"]


def test_off_strategy_prefers_owler_when_configured():
    merged = PreferredSourceMerger("owler").merge_profiles(craft_and_owler())
    assert merged.company_name == "Acme, Inc."


def test_preferred_uses_craft_without_any_model_call():
    """The preferred strategy answers from the preferred source, no model."""
    merged = build_merger("preferred", preferred_source="craft").merge_profiles(
        craft_and_owler()
    )
    assert merged.company_name == "Acme"


def test_preferred_falls_back_without_preferred_source():
    """Missing preferred source resolves via ingesting it (tested in nodes)."""
    records = [
        record(
            "owler",
            NEW,
            name="Acme, Inc.",
            key_executives=[KeyExecutive(name="Grace", title="CTO")],
        ),
    ]
    # The merger composite itself still resolves deterministically when handed
    # only non-preferred rows (graceful degradation at the merger layer).
    merged = build_merger("preferred", preferred_source="craft").merge_profiles(
        records
    )
    assert merged.company_name == "Acme, Inc."


def test_union_merges_without_llm():
    """The algorithmic strategy unions collections; newest scalars win."""
    records = [
        record(
            "owler",
            NEW,
            name="Acme, Inc.",
            company_funding_info=[
                CompanyFundingInfo(funding_round="Series B", funding_date="2024")
            ],
            key_executives=[KeyExecutive(name="Grace", title="CTO")],
        ),
        record(
            "craft",
            OLD,
            name="Acme",
            company_funding_info=[
                CompanyFundingInfo(funding_round="Series A", funding_date="2020")
            ],
            key_executives=[KeyExecutive(name="Ada", title="CEO")],
        ),
    ]
    merged = DeterministicUnionMerger().merge_profiles(records)
    assert merged.company_name == "Acme, Inc."
    assert sorted(e.name for e in merged.key_executives) == ["Ada", "Grace"]
    assert sorted(f.funding_round for f in merged.company_funding_info) == [
        "Series A",
        "Series B",
    ]


def test_union_falls_back_to_older_scalar_when_newest_is_empty():
    records = [
        record("owler", NEW, name=""),
        record("craft", OLD, name="Acme"),
    ]
    assert DeterministicUnionMerger().merge_profiles(records).company_name == "Acme"


def test_union_collapses_duplicates_without_llm():
    """Case-insensitive duplicates collapse without a model call."""
    records = [
        record("owler", NEW, key_executives=[KeyExecutive(name="ADA", title="CEO")]),
        record("craft", OLD, key_executives=[KeyExecutive(name="Ada", title="CEO")]),
    ]
    merged = DeterministicUnionMerger().merge_profiles(records)
    assert [e.name for e in merged.key_executives] == ["ADA"]


def test_llm_strategy_requires_a_factory():
    with pytest.raises(ValueError, match="needs an LLM"):
        build_merger("llm")


def test_unknown_strategy_falls_back_to_preferred():
    merged = build_merger(
        "definitely-not-a-strategy", preferred_source="craft"
    ).merge_profiles(craft_and_owler())
    assert merged.company_name == "Acme"


def test_empty_records_are_a_caller_error():
    for merger in (
        PreferredSourceMerger(),
        DeterministicUnionMerger(),
        build_merger("preferred"),
    ):
        with pytest.raises(ValueError):
            merger.merge_profiles([])




def test_merge_strategy_drives_scrape_scope(monkeypatch):
    """Single-source strategies scrape the preferred source; merging scrapes all."""
    from company_data.config import crawler_configs
    from company_data.pipeline.ingestion import IngestionPipeline

    monkeypatch.setattr(crawler_configs.MergeConfig, "PREFERRED_SOURCE", "craft")
    cases = {
        "off": (("craft",), False),
        "preferred": (("craft",), False),
        "union": (("craft", "owler"), True),
        "llm": (("craft", "owler"), True),
    }
    for strategy, (expected, needs_all) in cases.items():
        monkeypatch.setattr(crawler_configs.MergeConfig, "STRATEGY", strategy)
        assert IngestionPipeline._default_sources() == expected, strategy
        assert crawler_configs.MergeConfig.needs_all_sources() is needs_all, strategy

    # Explicit sources always win (e.g. backfill scripts).
    assert (
        IngestionPipeline(
            store=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            sources=("owler",),
        ).sources
        == ("owler",)
    )


def test_reads_are_scoped_to_the_preferred_source(monkeypatch):
    """Single-source strategies ignore stale rows from other sources."""
    from company_data.agent.nodes import _strategy_records

    monkeypatch.setattr(MergeConfig, "STRATEGY", "preferred")
    monkeypatch.setattr(MergeConfig, "PREFERRED_SOURCE", "craft")
    records = craft_and_owler()
    scoped = _strategy_records(records)
    assert [r.source_name for r in scoped] == ["craft"]

    # Preferred source absent: strict scoping yields nothing, so the caller
    # ingests the preferred source instead of serving the stale foreign row.
    assert _strategy_records([records[0]]) == []

    # Multi-source strategies keep every record.
    monkeypatch.setattr(MergeConfig, "STRATEGY", "llm")
    assert _strategy_records(records) == records

# ------------------------------------------------------- multi-company extract


def test_single_company_alias_stays_backward_compatible():
    """Old call sites passing only ``company_name`` get ``company_names`` free."""
    extracted = ExtractedData(company_name="Stripe", intent="funding_history")
    assert extracted.company_names == ["Stripe"]
    assert extracted.company_name == "Stripe"


def test_multi_company_list_syncs_the_alias():
    """New call sites passing ``company_names`` get ``company_name`` free."""
    extracted = ExtractedData(
        company_names=["Stripe", "Adyen"], intent="compare_funding"
    )
    assert extracted.company_name == "Stripe"
    assert extracted.company_names == ["Stripe", "Adyen"]


def test_empty_extraction_stays_empty():
    extracted = ExtractedData(intent="tell me a joke")
    assert extracted.company_names == []
    assert extracted.company_name == ""
