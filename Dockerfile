# Imagen para ejecutar la API en local con Docker (en AWS se usa Lambda, ver infra/).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY alembic-central.ini alembic-tenant.ini ./
COPY scripts ./scripts
RUN uv sync --locked --no-dev

EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev python scripts/bootstrap_database.py && uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
