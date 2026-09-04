"""
FastAPI exception handlers.

This module is the boundary between application errors and HTTP errors.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from base.errors import AppError

from error_mapping import get_http_status


logger = logging.getLogger(__name__)


async def app_error_handler(
    request: Request,
    exc: AppError,
) -> JSONResponse:
    """
    Convert an application error into a consistent HTTP response.
    """

    status = get_http_status(exc)

    logger.warning(
        "Application error: code=%s path=%s message=%s",
        exc.error_code,
        request.url.path,
        exc.message,
    )

    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-level exception handlers."""

    app.add_exception_handler(AppError, app_error_handler)