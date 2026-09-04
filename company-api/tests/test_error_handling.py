"""
Tests the exception -> JSON response contract itself, independent of any
real route. A throwaway app with routes that deliberately raise is mounted
here so this contract stays tested even before company-api has real
business routes to exercise it through.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from error_handlers import register_exception_handlers
from exceptions import AppError, NotFoundError, DuplicateRecordError


@pytest.fixture
def error_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/not-found")
    async def boom_not_found():
        raise NotFoundError("company techcorp.com not found", details={"uid": "techcorp.com"})

    @app.get("/boom/duplicate")
    async def boom_duplicate():
        raise DuplicateRecordError("company already exists")

    @app.get("/boom/unhandled")
    async def boom_unhandled():
        raise RuntimeError("something broke that we didn't anticipate")

    return TestClient(app, raise_server_exceptions=False)


class TestAppErrorHandling:
    def test_not_found_error_shape(self, error_client):
        response = error_client.get("/boom/not-found")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "not_found"
        assert body["message"] == "company techcorp.com not found"
        assert body["details"] == {"uid": "techcorp.com"}

    def test_duplicate_error_shape(self, error_client):
        response = error_client.get("/boom/duplicate")
        assert response.status_code == 409
        assert response.json()["error"] == "duplicate_record"

    def test_app_error_status_codes_are_respected(self):
        assert NotFoundError("x").status_code == 404
        assert DuplicateRecordError("x").status_code == 409
        assert AppError("x").status_code == 500  # base class default

    def test_unhandled_exception_returns_generic_500(self, error_client):
        response = error_client.get("/boom/unhandled")
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "internal_error"
        # message should NOT leak internal exception details to the client
        assert "something broke" not in body["message"]