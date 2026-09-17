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


class LLMProfileMerger(BaseMerger):
    """Reconciles per-source crawler records into one profile using an LLM.

    Stores keep one record per crawler source and never merge at rest; this
    merger runs only when a consumer explicitly requires a unified view.
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
            raise ValueError("No source records to merge.")
        if len(records) == 1:
            # Nothing to reconcile, so no model call is warranted. The agent
            # node applies the same rule; repeating it here keeps the merger
            # honest for any other caller.
            logger.info("Single source record: no reconciliation required.")
            return records[0].profile

        ranked = sorted(
            records,
            key=lambda record: self._as_utc(record.profile.last_scraped_at),
            reverse=True,
        )
        prompt: str = Prompts.PROFILE_MERGE_USER_PROMPT.format(
            company_domain=ranked[0].profile.company_domain,
            records_json=self._serialize_records(ranked),
            focus_query=focus_query or "none",
        )
        merged_subset = self.llm_client.generate_structured_output(
            prompt=prompt,
            response_schema=MergedProfile,
            system_instructions=self.system_prompt,
        )

        # Start from the freshest record (keeps fields outside the merge
        # scope, e.g. logo/status/socials) and overlay the reconciled data.
        payload = ranked[0].profile.model_dump()
        for key, value in merged_subset.model_dump().items():
            if value not in (None, "", [], {}):
                payload[key] = value

        try:
            merged = CompanyData.model_validate(payload)
        except Exception:
            logger.exception(
                "Merged output failed validation; falling back to the freshest record."
            )
            return ranked[0].profile
        return self._restore_missing_entries(ranked, self._deduplicate(merged))

    def _deduplicate(self, profile: CompanyData) -> CompanyData:
        """Collapses entries the model itself duplicated.

        No model de-duplicates perfectly - Gemini has been observed returning
        the same executive twice - and the LLM's list is authoritative, so a
        duplicate leaks straight into the merged view. Two entries sharing an
        identity are the same entry by the definitions in
        ``COLLECTION_IDENTITY``, so keeping the most complete one can never
        drop distinct data.
        """
        payload = profile.model_dump()
        collapsed = 0
        for field in COLLECTION_IDENTITY:
            kept: list[object] = []
            identities: list[tuple] = []
            for entry in payload.get(field) or []:
                identity = self._identity(field, entry)
                duplicate_of = next(
                    (
                        index
                        for index, existing in enumerate(identities)
                        if self._already_present(field, identity, [existing])
                    ),
                    None,
                )
                if duplicate_of is None:
                    kept.append(entry)
                    identities.append(identity)
                    continue
                collapsed += 1
                if self._information(entry) > self._information(kept[duplicate_of]):
                    kept[duplicate_of] = entry
                    identities[duplicate_of] = identity
            payload[field] = kept
        if collapsed:
            logger.info(f"Dropped {collapsed} duplicated collection entries.")
        return CompanyData.model_validate(payload)

    @classmethod
    def _information(cls, entry: object) -> int:
        """How many fields an entry actually populates."""
        payload = cls._as_payload(entry)
        if not isinstance(payload, dict):
            return 1
        return sum(1 for value in payload.values() if value not in (None, "", [], {}))

    def _restore_missing_entries(
        self, records: Sequence[SourcedProfile], merged: CompanyData
    ) -> CompanyData:
        """Completes every collection field to the full union across sources.

        Only the LLM's reconciliation is trusted for *which value wins* and
        for de-duplication; completeness is guaranteed here, so a model that
        omits entries (common for small local models on long lists) cannot
        cause data loss.
        """
        payload = merged.model_dump()
        restored = 0
        for field in COLLECTION_IDENTITY:
            entries = list(payload.get(field) or [])
            existing = [self._identity(field, entry) for entry in entries]
            for record in records:
                for entry in getattr(record.profile, field) or []:
                    identity = self._identity(field, entry)
                    if self._already_present(field, identity, existing):
                        continue
                    existing.append(identity)
                    entries.append(self._as_payload(entry))
                    restored += 1
            payload[field] = entries
        if restored:
            logger.info(
                f"Merge completed losslessly: restored {restored} collection "
                "entries the LLM omitted."
            )
        return CompanyData.model_validate(payload)

    @classmethod
    def _already_present(
        cls, field: str, candidate: tuple, existing: Sequence[tuple]
    ) -> bool:
        """Whether ``candidate`` is already represented by an existing entry."""
        if not COLLECTION_IDENTITY[field]:
            return candidate in existing
        return any(cls._identities_match(candidate, other) for other in existing)

    @staticmethod
    def _identities_match(left: tuple, right: tuple) -> bool:
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
        return all(not part or not other or part == other for part, other in zip(left, right))

    @classmethod
    def _identity(cls, field: str, entry: object) -> tuple:
        """Cross-source identity of one collection entry, case-insensitive."""
        identity_fields = COLLECTION_IDENTITY[field]
        payload = cls._as_payload(entry)
        if not identity_fields:
            return (cls._normalize(payload),)
        parts = tuple(cls._normalize(payload.get(name)) for name in identity_fields)
        if not any(parts):
            # No usable identity (e.g. an employee count without a period):
            # key it by its own content so distinct entries stay distinct.
            fingerprint = "#raw:" + json.dumps(payload, sort_keys=True, default=str)
            return (fingerprint,) * len(identity_fields)
        return parts

    @staticmethod
    def _normalize(value: object) -> str:
        """Case/whitespace-insensitive form used to match entries."""
        return " ".join(str(value or "").split()).lower()

    @staticmethod
    def _as_payload(entry: object) -> object:
        """Plain-JSON form of an entry, whether it is a model or a value."""
        return entry.model_dump() if hasattr(entry, "model_dump") else entry

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

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
