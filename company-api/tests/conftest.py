import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "company-common"))

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)