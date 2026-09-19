"""Non-LLM reconciliation: single-source selection plus deterministic union.

Everything here is free of model calls. Union semantics are shared: the
freshest record supplies scalars (falling back through older records for
missing values) and every collection field becomes the de-duplicated union,
reusing the identity rules from :mod:`llm_merger` so ``union`` and ``llm``
agree on what counts as the same entry.
"""

from collections.abc import Sequence

from company_data_crawler.models.company_data import CompanyData

from company_data.config.crawler_configs import MergeConfig
from company_data.database.base import SourcedProfile
from company_data.pipeline.interfaces.merger import BaseMerger
from company_data.pipeline.llm_merger import LLMProfileMerger, _CollectionCompletion
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class PreferredSourceMerger(BaseMerger):
    """Answers from the preferred source, deterministically, with no LLM call.

    Returns the preferred source's record when present; otherwise falls back
    to the freshest record (a ``preferred`` strategy never produces ``None``
    for a non-empty record set). A single record always passes through.
    """

    def __init__(self, preferred_source: str = MergeConfig.PREFERRED_SOURCE) -> None:
        self.preferred_source = (preferred_source or "").strip().lower()

    def merge_profiles(
        self, records: Sequence[SourcedProfile], focus_query: str | None = None
    ) -> CompanyData:
        if not records:
            raise ValueError("Cannot merge an empty record set.")
        for record in records:
            if (record.source_name or "").strip().lower() == self.preferred_source:
                logger.info(
                    f"Using {record.source_name} record "
                    f"({self.preferred_source} is preferred); no merge."
                )
                return record.profile
        newest_first = sorted(
            records,
            key=lambda record: _CollectionCompletion.as_utc(
                record.profile.last_scraped_at
            ),
            reverse=True,
        )
        logger.info(
            f"Preferred source {self.preferred_source!r} has no record; "
            f"falling back to the freshest record ({newest_first[0].source_name})."
        )
        return newest_first[0].profile


class DeterministicUnionMerger(_CollectionCompletion, BaseMerger):
    """Algorithmic (non-LLM) union across all sources.

    Scalars come from the freshest record that carries a non-empty value;
    collections become the de-duplicated, losslessly completed union, using the
    same identity rules as the LLM merger so both strategies agree on what
    counts as the same entry. ``focus_query`` is accepted for interface
    compatibility and ignored - an algorithm has no use for intent.
    """

    #: Scalar fields the union reconciles; the freshest non-empty value wins.
    SCALAR_FIELDS: tuple[str, ...] = (
        "company_name",
        "company_description",
        "company_founded_year",
        "company_type",
        "company_symbol",
        "company_website_url",
        "company_linkedin_url",
        "company_twitter_url",
    )

    def merge_profiles(
        self, records: Sequence[SourcedProfile], focus_query: str | None = None
    ) -> CompanyData:
        if not records:
            raise ValueError("Cannot merge an empty record set.")
        if len(records) == 1:
            return records[0].profile
        ranked = sorted(
            records,
            key=lambda record: self.as_utc(record.profile.last_scraped_at),
            reverse=True,
        )
        payload = ranked[0].profile.model_dump()
        for field in self.SCALAR_FIELDS:
            if self._is_empty(payload.get(field)):
                for record in ranked[1:]:
                    candidate = getattr(record.profile, field)
                    if not self._is_empty(candidate):
                        payload[field] = (
                            candidate.model_dump()
                            if hasattr(candidate, "model_dump")
                            else candidate
                        )
                        break
        return self.complete_collections(payload, records)

    @staticmethod
    def _is_empty(value: object) -> bool:
        return value in (None, "", [], {})

def build_merger(
    strategy: str | None = None,
    preferred_source: str | None = None,
    llm_factory=None,
) -> BaseMerger:
    """Builds the merger for a strategy name (see :class:`MergeConfig`).

    ``llm`` needs ``llm_factory`` (a callable returning the merge LLM), so the
    optional LLM dependency is only constructed when the strategy requires it.
    Unknown strategies fall back to ``preferred``.
    """
    resolved = (strategy or MergeConfig.validated_strategy()).strip().lower()
    preferred = preferred_source or MergeConfig.PREFERRED_SOURCE
    if resolved == "off":
        return PreferredSourceMerger(preferred)
    if resolved == "preferred":
        return _PreferredWithUnionFallback(preferred)
    if resolved == "llm":
        if llm_factory is None:
            raise ValueError("The 'llm' merge strategy needs an LLM: pass llm_factory.")
        from company_data.pipeline.llm_merger import LLMProfileMerger

        return LLMProfileMerger(llm_factory())
    # "union" and anything unknown (safe default: no model call).
    if resolved != "union":
        logger.warning(f"Unknown merge strategy {resolved!r}; falling back to 'preferred'.")
        return _PreferredWithUnionFallback(preferred)
    return DeterministicUnionMerger()


class _PreferredWithUnionFallback(BaseMerger):
    """``preferred`` strategy: preferred source, else deterministic union.

    Keeps :class:`PreferredSourceMerger` itself a pure single-record selector
    (useful for ``off``), while this composite adds the union fallback.
    """

    def __init__(self, preferred_source: str = MergeConfig.PREFERRED_SOURCE) -> None:
        self.preferred = PreferredSourceMerger(preferred_source)
        self.union = DeterministicUnionMerger()

    def merge_profiles(
        self, records: Sequence[SourcedProfile], focus_query: str | None = None
    ) -> CompanyData:
        if not records:
            raise ValueError("Cannot merge an empty record set.")
        wanted = (self.preferred.preferred_source or "").strip().lower()
        if any((r.source_name or "").strip().lower() == wanted for r in records):
            return self.preferred.merge_profiles(records, focus_query)
        logger.info(
            f"Preferred source {wanted!r} has no record; "
            "falling back to the deterministic union."
        )
        return self.union.merge_profiles(records, focus_query)

