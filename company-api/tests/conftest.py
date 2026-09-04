import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def test_app():
    return create_app()


@pytest.fixture
def client(test_app):
    return TestClient(test_app)