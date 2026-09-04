"""
Maps application errors to HTTP status codes.

This module belongs to company-api because HTTP is a transport concern.
The shared company-common package must remain independent of HTTP.
"""

from http import HTTPStatus

from base.errors import (
    AppError,
    DatabaseError,
    DuplicateRecordError,
    NotFoundError,
    UpstreamSourceError,
    ValidationFailedError,
)


ERROR_STATUS_MAP: dict[type[AppError], HTTPStatus] = {
    NotFoundError: HTTPStatus.NOT_FOUND,
    DuplicateRecordError: HTTPStatus.CONFLICT,
    ValidationFailedError: HTTPStatus.UNPROCESSABLE_ENTITY,
    DatabaseError: HTTPStatus.SERVICE_UNAVAILABLE,
    UpstreamSourceError: HTTPStatus.BAD_GATEWAY,
}


def get_http_status(error: AppError) -> HTTPStatus:
    """
    Return the HTTP status associated with an application error.

    Unknown AppError subclasses are treated as internal server errors.
    """

    for error_type, status in ERROR_STATUS_MAP.items():
        if isinstance(error, error_type):
            return status

    return HTTPStatus.INTERNAL_SERVER_ERROR