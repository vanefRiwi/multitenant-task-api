from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config.logging import configure_logging
from app.config.settings import Settings, get_settings
from app.infrastructure.container import Container
from app.presentation.http.dependencies import get_container
from app.presentation.http.error_handlers import register_error_handlers
from app.presentation.http.middleware import request_context_middleware
from app.presentation.http.router import api_router


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Multitenant Task Management API",
        version="1.0.0",
        description=(
            "API RESTful multitenant de tareas. Cada organización (tenant) tiene su propia "
            "base de datos PostgreSQL. Autentícate en /api/v1/auth/login y usa el token "
            "con el botón **Authorize**."
        ),
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url="/redoc" if settings.expose_docs else None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
    )
    # Recursos compartidos del proceso (se crean de forma perezosa en la primera petición).
    app.state.settings = settings
    app.state.container = container

    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"], response_model=None)
    def readiness(request: Request) -> Any:
        """Comprueba que la API llega a control_db (para smoke tests y monitoreo)."""
        container = get_container(request)
        with container.central_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready"})

    return app


app = create_app()
