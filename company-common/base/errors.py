"""
Shared application error hierarchy.

This module is framework-agnostic.

It must not depend on:
- FastAPI
- HTTP
- DuckDB
- Crawlee
- any other infrastructure component

Transport-specific layers are responsible for translating these
application errors into their own error representation.
"""

from typing import Any, Dict, Optional


class AppError(Exception):
    """Base class for all expected application-level failures."""

    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    """Requested resource does not exist."""

    error_code = "not_found"


class DuplicateRecordError(AppError):
    """Attempted to create a record that already exists."""

    error_code = "duplicate_record"


class ValidationFailedError(AppError):
    """Data failed domain-level validation."""

    error_code = "validation_failed"


class DatabaseError(AppError):
    """An expected storage/database operation failed."""

    error_code = "database_error"


class UpstreamSourceError(AppError):
    """An external data source failed or returned unusable data."""

    error_code = "upstream_source_error"