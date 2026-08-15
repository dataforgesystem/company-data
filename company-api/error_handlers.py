"""
Exception handler registration for company-api.

Kept separate from main.py so tests can mount these handlers on a
throwaway FastAPI app without needing the full production app (real DB
connection, all routes, etc) - see tests/test_error_handling.py.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from exceptions import AppError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error",
            extra={"error_code": exc.error_code, "path": str(request.url), "details": exc.details},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"path": str(request.url)})
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "An unexpected error occurred", "details": {}},
        )