import json
from collections.abc import Sequence
from datetime import datetime, timezone

from company_data_crawler.models.company_data import (
    CompanyData,
    CompanyEmployeeCount,
    CompanyFundingInfo,
    CompanyLocation,
    CompanyOperatingMetric,
    IncomeStatement,
    KeyExecutive,
    SimilarCompany,
)
from pydantic import BaseModel

from company_data.config.llm_configs import Prompts
from company_data.database.base import SourcedProfile
from company_data.llm.base import ILLMProvider
from company_data.pipeline.interfaces.merger import BaseMerger
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()


class MergedProfile(BaseModel):
    """Reduced reconciliation output for the merge LLM.

    Deliberately much smaller than ``CompanyData``: the grammar a small
    local model must satisfy shrinks drastically, which is what makes
    reliable merges possible. Everything else is inherited from the
    freshest record.
    """

    company_name: str = ""
    company_description: str | None = None
    company_founded_year: int | None = None
    company_type: str | None = None
    company_symbol: str | None = None
    company_website_url: str | None = None
    company_linkedin_url: str | None = None
    company_twitter_url: str | None = None
    company_industries: list[str] = []
    company_funding_info: list[CompanyFundingInfo] = []
    key_executives: list[KeyExecutive] = []
    company_employee_counts: list[CompanyEmployeeCount] = []
    company_locations: list[CompanyLocation] = []
    company_income_statements: list[IncomeStatement] = []
    similar_companies: list[SimilarCompany] = []
    company_operating_metrics: list[CompanyOperatingMetric] = []


# Fields that are reconciled as a union across sources, and the sub-fields
# that give an entry its cross-source identity. An empty tuple marks a plain
# list of strings matched by its own value.
COLLECTION_IDENTITY: dict[str, tuple[str, ...]] = {
    "company_industries": (),
    "company_funding_info": ("funding_round", "funding_date"),
    "key_executives": ("name",),
    "company_employee_counts": ("year", "month"),
    "company_locations": ("city", "country", "address"),
    "company_income_statements": ("end_date", "period_type"),
    "similar_companies": ("company_name",),
    "company_operating_metrics": ("company_specific_kpi", "date"),
}


class _CollectionCompletion:
    """Shared union logic for completing collection fields across sources.

    Both the LLM merger and the deterministic union merger build on this, so
    the two strategies agree on what counts as "the same entry" and neither
    can lose data a source provided.
    """

    @classmethod
    def complete_collections(
        cls,
        payload: dict,
        records: Sequence[SourcedProfile],
        restored_label: str = "Merge completed",
    ) -> CompanyData:
        """Completes every collection field to the de-duplicated union."""
        restored = 0
        for field in COLLECTION_IDENTITY:
            entries = list(payload.get(field) or [])
            existing = [cls.identity(field, entry) for entry in entries]
            for record in records:
                for entry in getattr(record.profile, field) or []:
                    identity = cls.identity(field, entry)
                    if cls.already_present(field, identity, existing):
                        continue
                    existing.append(identity)
                    entries.append(cls.as_payload(entry))
                    restored += 1
            payload[field] = entries
        if restored:
            logger.info(
                f"{restored_label}: restored {restored} collection "
                "entries missing from the reconciled output."
            )
        return CompanyData.model_validate(payload)

    @classmethod
    def already_present(
        cls, field: str, candidate: tuple, existing: Sequence[tuple]
    ) -> bool:
        """Whether ``candidate`` is already represented by an existing entry."""
        if not COLLECTION_IDENTITY[field]:
            return candidate in existing
        return any(cls.identities_match(candidate, other) for other in existing)

    @staticmethod
    def identities_match(left: tuple, right: tuple) -> bool:
        """Whether two identities denote the same entry.

        A sub-field missing on *either* side acts as a wildcard: a model that
        echoes only part of an entry (e.g. a funding round without its date)
        still matches the fully populated source entry, so the union gains no
        spurious duplicates. When either identity is entirely empty there is
        nothing reliable to match on, so exact equality is required and an
        unrelated entry can never be swallowed.
        """
        if not any(left) or not any(right):
            return left == right
        return all(
            not part or not other or part == other for part, other in zip(left, right)
        )

    @classmethod
    def identity(cls, field: str, entry: object) -> tuple:
        """Cross-source identity of one collection entry, case-insensitive."""
        identity_fields = COLLECTION_IDENTITY[field]
        payload = cls.as_payload(entry)
        if not identity_fields:
            return (cls.normalize(payload),)
        parts = tuple(cls.normalize(payload.get(name)) for name in identity_fields)
        if not any(parts):
            # No usable identity (e.g. an employee count without a period):
            # key it by its own content so distinct entries stay distinct.
            fingerprint = "#raw:" + json.dumps(payload, sort_keys=True, default=str)
            return (fingerprint,) * len(identity_fields)
        return parts

    @staticmethod
    def normalize(value: object) -> str:
        """Case/whitespace-insensitive form used to match entries."""
        return " ".join(str(value or "").split()).lower()

    @staticmethod
    def as_payload(entry: object) -> object:
        """Plain-JSON form of an entry, whether it is a model or a value."""
        return entry.model_dump() if hasattr(entry, "model_dump") else entry

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def richness(entry: object) -> int:
        """Counts non-empty fields in a payload entry (dict or model)."""
        data = entry.model_dump() if hasattr(entry, "model_dump") else entry
        if not isinstance(data, dict):
            return 1 if data not in (None, "") else 0
        return sum(1 for value in data.values() if value not in (None, "", [], {}))


class LLMProfileMerger(_CollectionCompletion, BaseMerger):
    """Reconciles per-source crawler records into one profile using an LLM.

    This is the *optional* LLM merge strategy: it runs only when merging is
    enabled *and* the ``llm`` strategy is explicitly selected. Stores keep one
    record per crawler source and never merge at rest.

    The LLM fills the reduced ``MergedProfile`` schema (constrained output),
    and the result is mapped onto the freshest record, which contributes
    everything the merge does not cover (logo, status, socials, ...).

    The LLM owns the reconciliation *decisions* (conflicting scalars, how
    entries are de-duplicated, what matters for the consumer's query). Small
    local models cannot reliably transcribe long lists, so a weak model will
    silently drop entries; :meth:`_restore_missing_entries` therefore appends
    anything a source provided that the model omitted. The merge stays
    LLM-driven, but it can never lose data.
    """

    def __init__(self, llm: ILLMProvider) -> None:
        self.llm_client = llm
        self.system_prompt: str = Prompts.PROFILE_MERGE_SYSTEM_PROMPT

    def merge_profiles(
        self, records: Sequence[SourcedProfile], focus_query: str | None = None
    ) -> CompanyData:
        if not records:
            raise ValueError("Cannot merge an empty record set.")
        if len(records) == 1:
            return records[0].profile
        try:
            ranked = sorted(
                records,
                key=lambda record: self.as_utc(record.profile.last_scraped_at),
                reverse=True,
            )
            prompt: str = Prompts.PROFILE_MERGE_USER_PROMPT.format(
                company_domain=ranked[0].profile.company_domain,
                records_json=self._serialize_records(ranked),
                focus_query=focus_query or "none",
            )
            response_merged_profile: MergedProfile = (
                self.llm_client.generate_structured_output(
                    prompt=prompt,
                    response_schema=MergedProfile,
                    system_instructions=self.system_prompt,
                )
            )
            deduped = self._deduplicate(response_merged_profile)
            payload = ranked[0].profile.model_dump()
            payload.update(deduped.model_dump(exclude_none=False))
            merged = CompanyData.model_validate(payload)
            return self._restore_missing_entries(ranked, merged)
        except Exception:
            logger.exception(
                "LLM merge failed; falling back to the freshest record."
            )
            ranked = sorted(
                records,
                key=lambda record: self.as_utc(record.profile.last_scraped_at),
                reverse=True,
            )
            return ranked[0].profile

    def _deduplicate(self, profile: MergedProfile) -> MergedProfile:
        """Collapses entries sharing an identity, keeping the richest one.

        A model may echo the same entry twice (e.g. ``John Collison`` from two
        sources); without this, duplicates leak into the output. The surviving
        entry is the one carrying the most detail (most non-empty fields),
        with ties broken towards the first occurrence.
        """
        payload = profile.model_dump()
        merged = False
        for field in COLLECTION_IDENTITY:
            entries = list(payload.get(field) or [])
            if len(entries) < 2:
                continue
            kept: list = []
            kept_identities: list[tuple] = []
            for entry in entries:
                identity = self.identity(field, entry)
                match_index = next(
                    (
                        index
                        for index, existing in enumerate(kept_identities)
                        if self.already_present(field, identity, [existing])
                    ),
                    None,
                )
                if match_index is None:
                    kept.append(entry)
                    kept_identities.append(identity)
                elif self.richness(entry) > self.richness(kept[match_index]):
                    kept[match_index] = entry
            if len(kept) != len(entries):
                payload[field] = kept
                merged = True
        if merged:
            logger.info("Dropped duplicated collection entries the LLM emitted.")
        return MergedProfile.model_validate(payload)

    def _restore_missing_entries(
        self, records: Sequence[SourcedProfile], merged: CompanyData
    ) -> CompanyData:
        """Completes every collection field to the full union across sources.

        Only the LLM's reconciliation is trusted for *which value wins* and
        for de-duplication; completeness is guaranteed here, so a model that
        omits entries (common for small local models on long lists) cannot
        cause data loss.
        """
        return self.complete_collections(
            merged.model_dump(), records, restored_label="Merge completed losslessly"
        )

    def _serialize_records(self, records: Sequence[SourcedProfile]) -> str:
        """JSON payload for the LLM: most recently scraped record first.

        Empty/default fields are stripped so the model sees only real data
        (small models handle much smaller prompts more reliably).
        """
        labeled = [
            {
                "source_name": record.source_name,
                "last_scraped_at": record.profile.last_scraped_at.isoformat(),
                "profile": self._strip_empty(record.profile.model_dump(mode="json")),
            }
            for record in records
        ]
        return json.dumps(labeled, indent=2)

    @staticmethod
    def _strip_empty(value: object) -> object:
        """Recursively drops None/''/[]/{} entries from decoded JSON data."""
        if isinstance(value, dict):
            cleaned = {
                key: LLMProfileMerger._strip_empty(item)
                for key, item in value.items()
            }
            return {
                key: item
                for key, item in cleaned.items()
                if item not in (None, "", [], {})
            }
        if isinstance(value, list):
            cleaned_items = [LLMProfileMerger._strip_empty(item) for item in value]
            return [item for item in cleaned_items if item not in (None, "", [], {})]
        return value
