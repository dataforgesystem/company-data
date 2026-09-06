"""
Company API entrypoint.

Deliberately minimal right now - no DB dependency, no business routes yet.

The application factory keeps application construction in one place so
production and tests use the same application configuration.
"""

from fastapi import FastAPI

from error_handlers import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Company API",
        version="0.1.0",
    )

    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()