"""Guards the UI decoupling promise.

The chat UI (``ui/``) is the only place that may import a UI framework; the
core package in ``src/company_data`` must stay importable with no UI
installed. Deleting ``ui/`` and uninstalling Chainlit must never break the
pipeline, so this test fails if a UI import ever creeps into the core.
"""

from pathlib import Path

CORE_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "company_data"


def test_core_package_never_imports_a_ui_framework():
    offenders = [
        str(path.relative_to(CORE_PACKAGE.parents[1]))
        for path in sorted(CORE_PACKAGE.rglob("*.py"))
        if "chainlit" in path.read_text(encoding="utf-8").lower()
    ]
    assert offenders == []