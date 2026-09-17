"""Shared test fixtures."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Runs ``@pytest.mark.anyio`` tests on asyncio only.

    ``anyio`` (a transitive dependency) provides the plugin, so async tests
    need no extra test dependency.
    """
    return "asyncio"