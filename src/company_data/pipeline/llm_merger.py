import json
from collections.abc import Sequence
from datetime import datetime, timezone

from company_data_crawler.models.company_data import CompanyData

from company_data.config.llm_configs import Prompts
from company_data.database.base import SourcedProfile
from company_data.llm.base import LLMProvider
from company_data.pipeline.interfaces.merger import BaseMerger


class LLMProfileMerger(BaseMerger):
    """Reconciles per-source crawler records into one profile using an LLM.

    Stores keep one record per crawler source and never merge at rest; this
    merger runs only when a consumer explicitly requires a unified view.
    Structured output is constrained to the ``CompanyData`` JSON schema, so
    the LLM cannot return records that fail validation.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm_client = llm
        self.system_prompt: str = Prompts.PROFILE_MERGE_SYSTEM_PROMPT

    def merge_profiles(
        self, records: Sequence[SourcedProfile], focus_query: str | None = None
    ) -> CompanyData:
        if not records:
            raise ValueError("No source records to merge.")

        prompt: str = Prompts.PROFILE_MERGE_USER_PROMPT.format(
            company_domain=records[0].profile.company_domain,
            records_json=self._serialize_records(records),
            focus_query=focus_query or "none",
        )
        return self.llm_client.generate_structured_output(
            prompt=prompt,
            response_schema=CompanyData,
            system_instructions=self.system_prompt,
        )

    def _serialize_records(self, records: Sequence[SourcedProfile]) -> str:
        """JSON payload for the LLM: most recently scraped record first."""
        ranked = sorted(
            records,
            key=lambda record: self._as_utc(record.profile.last_scraped_at),
            reverse=True,
        )
        labeled = [
            {
                "source_name": record.source_name,
                "last_scraped_at": record.profile.last_scraped_at.isoformat(),
                "profile": record.profile.model_dump(mode="json"),
            }
            for record in ranked
        ]
        return json.dumps(labeled, indent=2)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
