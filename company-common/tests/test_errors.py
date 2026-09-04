import pytest

from base import (
    AppError,
    DatabaseError,
    DuplicateRecordError,
    NotFoundError,
    UpstreamSourceError,
    ValidationFailedError,
)


class TestAppError:
    def test_message_is_preserved(self):
        error = AppError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"

    def test_default_error_code(self):
        error = AppError("Something went wrong")

        assert error.error_code == "internal_error"

    def test_details_default_to_empty_dict(self):
        error = AppError("Something went wrong")

        assert error.details == {}

    def test_details_are_preserved(self):
        details = {"company_id": "123"}

        error = AppError(
            "Company operation failed",
            details=details,
        )

        assert error.details == details


@pytest.mark.parametrize(
    ("error_class", "expected_code"),
    [
        (NotFoundError, "not_found"),
        (DuplicateRecordError, "duplicate_record"),
        (ValidationFailedError, "validation_failed"),
        (DatabaseError, "database_error"),
        (UpstreamSourceError, "upstream_source_error"),
    ],
)
def test_error_codes_are_stable(error_class, expected_code):
    error = error_class("Test error")

    assert isinstance(error, AppError)
    assert error.error_code == expected_code


def test_errors_do_not_contain_http_status_code():
    error = NotFoundError("Company not found")

    assert not hasattr(error, "status_code")