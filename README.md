# Multitenant Task Management API

API RESTful para gestionar tareas de varias organizaciones (tenants) en una misma plataforma.
Cada organización tiene **su propia base de datos PostgreSQL**; una base central (`control_db`)
guarda usuarios, organizaciones y membresías.

**Stack:** Python 3.12 · FastAPI · SQLModel · Alembic · uv · PostgreSQL · Pytest + HTTPX ·
Docker · AWS Lambda + API Gateway · RDS · Secrets Manager · AWS SAM · GitHub Actions (OIDC) ·
Cloudflare DNS.

## Documentación

Está escrita para alguien que **nunca ha hecho esto**, en orden:

| # | Documento | Qué encontrarás |
|---|-----------|-----------------|
| 1 | [Arquitectura y código](docs/01-arquitectura.md) | Cómo está organizado el proyecto, qué hace cada capa y cómo viaja una petición |
| 2 | [Desarrollo local](docs/02-desarrollo-local.md) | Instalar herramientas, levantar la API en tu máquina y correr las pruebas |
| 3 | [Setup en AWS paso a paso](docs/03-setup-aws.md) | Cuenta, IAM, RDS, Secrets Manager, SAM, OIDC, ACM, API Gateway y Cloudflare |
| 4 | [Probar que el multitenant funciona](docs/04-probar-multitenant.md) | Dos usuarios, dos organizaciones y verificación del aislamiento, en local y en AWS |
| 5 | [OAuth con Google y GitHub](docs/05-oauth-google-github.md) | Qué tendrías que hacer y si conviene en este MVP |
| 6 | [Preguntas frecuentes y decisiones](docs/06-preguntas-y-decisiones.md) | Unit testing, RDS Proxy, costes y otras decisiones |

## Arranque rápido (local)

```bash
cp .env.example .env
docker compose up -d db                      # PostgreSQL 16
uv sync                                      # dependencias (uv.lock)
uv run python scripts/bootstrap_database.py  # roles, control_db y migraciones
uv run uvicorn app.main:app --reload         # http://localhost:8000/docs
```

Pruebas:

```bash
uv run pytest tests/integration
uv run pytest tests/api
uv run pytest tests/security
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Endpoints

Todos bajo `/api/v1`. Documentación interactiva en `/docs` (OpenAPI).

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/register` | Registro (email + contraseña) |
| POST | `/auth/login` | Devuelve un JWT |
| GET | `/auth/me` | Usuario autenticado |
| POST | `/tenants` | Crear organización (crea su base de datos; el creador es `owner`) |
| GET | `/tenants` | Organizaciones a las que perteneces |
| GET | `/tenants/{tenant_id}` | Una organización |
| GET/POST | `/tenants/{tenant_id}/members` | Listar / añadir miembros (añadir: solo `owner`) |
| PATCH/DELETE | `/tenants/{tenant_id}/members/{user_id}` | Cambiar rol / revocar acceso |
| POST/GET | `/tenants/{tenant_id}/tasks` | Crear / listar tareas (`limit`, `offset`, `status`, `priority`) |
| GET/PATCH/DELETE | `/tenants/{tenant_id}/tasks/{task_id}` | Consultar / actualizar / eliminar |
| GET | `/health`, `/health/ready` | Salud del proceso / conexión con la base de datos |

## Estructura

```
src/app/
├── domain/          # Entidades, enums, excepciones, contratos (repositorios y puertos)
├── application/     # Casos de uso (auth, tenants, memberships, tasks)
├── infrastructure/  # SQLModel, repositorios, JWT, Argon2, secretos, provisión, conexiones
├── presentation/    # FastAPI: routers, schemas, dependencias, manejador de errores
├── config/          # Settings y logging
├── main.py          # App FastAPI
├── handler.py       # Entrada de Lambda (API)
└── ops_handler.py   # Entrada de Lambda (operaciones: bootstrap y migraciones)
migrations/central   # Alembic de control_db
migrations/tenant    # Alembic de cada base de tenant
infra/               # template.yaml (SAM) y github-oidc.yaml
scripts/             # bootstrap, provisión, migración de tenants, smoke test
tests/               # integration/, api/, security/
```
