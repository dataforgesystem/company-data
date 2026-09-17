from abc import ABC, abstractmethod
from collections.abc import Sequence

from company_data_crawler.models.company_data import CompanyData

from company_data.database.base import SourcedProfile


class BaseMerger(ABC):
    """Contract for reconciling per-source crawler records on demand.

    Stores keep one record per crawler source and never merge at rest;
    a merger is invoked only when a consumer explicitly requires a
    unified profile.
    """

    @abstractmethod
    def merge_profiles(
        self, records: Sequence[SourcedProfile], focus_query: str | None = None
    ) -> CompanyData:
        """Reconcile per-source records into one unified company profile.

        Args:
            records: Per-source records for a single company.
            focus_query: Optional reason the profile is needed (e.g. the
                user query that triggered the merge), so reconciliation can
                prioritize the fields that matter for it.
        """
