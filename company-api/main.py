"""
company-api entrypoint.

Deliberately minimal right now - no DB dependency, no business routes yet.
This exists so error-handling conventions have somewhere to attach and
get tested before routes/DB integration land on top.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "company-common"))

from fastapi import FastAPI

from error_handlers import register_exception_handlers

app = FastAPI(title="Company API", version="0.1.0")
register_exception_handlers(app)


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}