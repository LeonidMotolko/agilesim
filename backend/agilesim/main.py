"""FastAPI application entry point: ``uvicorn agilesim.main:app``."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agilesim.config import DEFAULT_JWT_SECRET, ENV_DEVELOPMENT, get_settings
from agilesim.core.errors import register_error_handlers
from agilesim.core.logging import configure_logging, install_request_logging
from agilesim.db.session import get_engine


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.app_env != ENV_DEVELOPMENT and settings.jwt_secret == DEFAULT_JWT_SECRET:
        msg = "AGILESIM_JWT_SECRET must be set outside the development environment"
        raise RuntimeError(msg)
    configure_logging(settings.log_level)
    app = FastAPI(title="AgileSim API", version="0.1.0", debug=settings.app_env == ENV_DEVELOPMENT)
    install_request_logging(app)
    register_error_handlers(app)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness probe used by Docker Compose and CI smoke checks."""
        return {"status": "ok"}

    @app.get("/health/db", tags=["system"])
    def health_db() -> JSONResponse:
        """Readiness probe: 200 when the database answers, 503 otherwise."""
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except (RuntimeError, SQLAlchemyError):
            return JSONResponse({"database": "unavailable"}, status_code=503)
        return JSONResponse({"database": "ok"})

    return app


app = create_app()
