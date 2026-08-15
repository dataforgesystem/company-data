"""
Shared exception hierarchy (company-common).

Repository, service, and crawler code raises these instead of generic
Exceptions or DB-specific errors. company-api catches AppError once, at
the top, and turns it into a consistent JSON error response - no route
handler needs its own try/except for expected failure cases.

Keep this file free of framework imports (no FastAPI, no duckdb) - it has
to be importable by every package, including ones that never touch HTTP.
"""

from typing import Any, Optional


class AppError(Exception):
    """Base class for all expected application errors.

    status_code: the HTTP status the API layer should respond with.
    error_code: a stable, machine-readable string for API consumers to
        branch on - don't rely on the human-readable message for that.
    """

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    """Requested resource doesn't exist, e.g. get(uid) found nothing."""

    status_code = 404
    error_code = "not_found"


class DuplicateRecordError(AppError):
    """Attempted to create a record that already exists under a unique key."""

    status_code = 409
    error_code = "duplicate_record"


class ValidationFailedError(AppError):
    """Input failed domain-level validation beyond what Pydantic checks
    (e.g. business rules), as opposed to malformed request payloads -
    FastAPI/Pydantic already handle those with their own 422s."""

    status_code = 422
    error_code = "validation_failed"


class DatabaseError(AppError):
    """Underlying storage layer failed (connection issue, constraint
    violation that isn't a simple duplicate, etc)."""

    status_code = 503
    error_code = "database_error"


class UpstreamSourceError(AppError):
    """A data source (crawler target, third-party API) failed or returned
    something unusable. Distinct from DatabaseError since the fix and the
    retry strategy are different."""

    status_code = 502
    error_code = "upstream_source_error"