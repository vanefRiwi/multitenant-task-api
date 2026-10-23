# Uso local:
#   make dev        -> levanta PostgreSQL (docker) + bootstrap + API con recarga
#   make test       -> todas las pruebas (necesita PostgreSQL)
#   make lint       -> formato, lint y tipos
#
# AWS SAM llama a los objetivos build-<Función> (BuildMethod: makefile en infra/template.yaml)
# para construir el paquete de Lambda: dependencias para Linux x86_64 + código + migraciones.

.PHONY: dev db bootstrap run test lint sam-build

db:
	docker compose up -d db

bootstrap:
	uv run python scripts/bootstrap_database.py

run:
	uv run uvicorn app.main:app --reload

dev: db bootstrap run

test:
	uv run pytest tests/integration tests/api tests/security

lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy

sam-build:
	sam build --template-file infra/template.yaml --build-in-source

build-ApiFunction build-OpsFunction:
	uv export --frozen --no-dev --no-editable --no-hashes --no-emit-project -o requirements-lambda.txt
	uv pip install --quiet --target "$(ARTIFACTS_DIR)" --python-version 3.12 \
		--python-platform x86_64-manylinux_2_28 --only-binary :all: -r requirements-lambda.txt
	cp -r src/app "$(ARTIFACTS_DIR)/app"
	cp -r migrations alembic-central.ini alembic-tenant.ini "$(ARTIFACTS_DIR)/"
	rm -f requirements-lambda.txt
