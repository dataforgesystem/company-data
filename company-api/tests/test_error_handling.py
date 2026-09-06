import pytest

from base.errors import (
    DatabaseError,
    DuplicateRecordError,
    NotFoundError,
    UpstreamSourceError,
    ValidationFailedError,
)


@pytest.mark.parametrize(
    (
        "error_class",
        "expected_status",
        "expected_code",
    ),
    [
        (NotFoundError, 404, "not_found"),
        (DuplicateRecordError, 409, "duplicate_record"),
        (ValidationFailedError, 422, "validation_failed"),
        (DatabaseError, 503, "database_error"),
        (UpstreamSourceError, 502, "upstream_source_error"),
    ],
)
def test_application_error_mapping(
    test_app,
    client,
    error_class,
    expected_status,
    expected_code,
):
    @test_app.get("/test-error")
    async def raise_error():
        raise error_class("Test error")

    response = client.get("/test-error")

    assert response.status_code == expected_status

    body = response.json()

    assert body["error"]["code"] == expected_code
    assert body["error"]["message"] == "Test error"


def test_error_details_are_preserved(test_app, client):
    @test_app.get("/test-error")
    async def raise_error():
        raise NotFoundError(
            "Company not found",
            details={"company_id": "123"},
        )

    response = client.get("/test-error")

    assert response.status_code == 404

    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Company not found",
            "details": {
                "company_id": "123",
            },
        }
    }