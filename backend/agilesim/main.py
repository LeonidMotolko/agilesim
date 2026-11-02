"""FastAPI application entry point: ``uvicorn agilesim.main:app``."""

from fastapi import FastAPI

from agilesim.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AgileSim API", version="0.1.0", debug=settings.app_env == "development")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness probe used by Docker Compose and CI smoke checks."""
        return {"status": "ok"}

    return app


app = create_app()
