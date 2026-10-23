# 2. Desarrollo local paso a paso

Objetivo: tener la API funcionando en tu computadora en unos 15 minutos.

## 2.1. Instala las herramientas (una sola vez)

| Herramienta | Para qué | Cómo instalar |
|-------------|----------|---------------|
| Git | Clonar el repo | <https://git-scm.com/downloads> |
| Docker Desktop | Ejecutar PostgreSQL sin instalarlo | <https://www.docker.com/products/docker-desktop/> |
| uv | Python, dependencias y entorno virtual | macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` · Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

No hace falta instalar Python: `uv` descarga la versión correcta (3.12) automáticamente.

Comprueba:

```bash
git --version
docker --version
uv --version
```

## 2.2. Clona y prepara el proyecto

```bash
git clone https://github.com/vanefRiwi/multitenant-task-api.git
cd multitenant-task-api
uv sync                # crea .venv e instala exactamente lo que dice uv.lock
cp .env.example .env   # configuración local (en Windows: copy .env.example .env)
```

Abre `.env` y cambia `JWT_SECRET` por un valor largo. Puedes generarlo así:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2.3. Levanta PostgreSQL

```bash
docker compose up -d db
docker compose ps        # espera a que "db" diga "healthy"
```

Esto arranca PostgreSQL 16 en `localhost:5432` con el superusuario `postgres` / `postgres`
(solo para tu máquina).

## 2.4. Prepara la base central (bootstrap)

```bash
uv run python scripts/bootstrap_database.py
```

Qué hace (es seguro repetirlo):

1. Crea el rol `app_central` (el que usa la API para `control_db`, solo lectura/escritura de
   filas).
2. Crea el rol `tenant_provisioner` (puede crear bases y roles, **no** es superusuario).
3. Crea la base `control_db` y deja que solo `app_central` se conecte.
4. Aplica `migrations/central` y da los permisos mínimos.

Deberías ver algo como:

```json
{ "control_db": "control_db", "central_revision": "0001_control_plane" }
```

## 2.5. Arranca la API

```bash
uv run uvicorn app.main:app --reload
```

- Documentación interactiva: <http://localhost:8000/docs>
- Salud: <http://localhost:8000/health> y <http://localhost:8000/health/ready>

### Probarla desde `/docs` (Swagger)

1. `POST /api/v1/auth/register` → *Try it out* → `{"email": "ana@example.com", "password": "una-clave-segura"}`.
2. `POST /api/v1/auth/login` con lo mismo → copia `access_token`.
3. Botón **Authorize** (arriba a la derecha) → pega el token → *Authorize*.
4. `POST /api/v1/tenants` → `{"name": "Acme", "slug": "acme"}` → copia el `id`.
5. `POST /api/v1/tenants/{tenant_id}/tasks` → `{"title": "Mi primera tarea"}`.

La guía completa para comprobar el aislamiento está en
[04-probar-multitenant.md](04-probar-multitenant.md).

### Alternativa: API también en Docker

```bash
docker compose --profile api up --build
```

## 2.6. Pruebas, lint y tipos

Las pruebas usan el PostgreSQL de Docker, pero crean **sus propias** bases con prefijo
`test_` y las borran al terminar: no tocan tu `control_db` de desarrollo.

```bash
uv run pytest tests/integration   # repositorios, sesiones, PostgreSQL, migraciones
uv run pytest tests/api           # endpoints, validación, códigos HTTP
uv run pytest tests/security      # tokens, aislamiento, permisos, fugas de información
uv run pytest                     # todo junto (~30 s)

uv run ruff format --check .      # formato
uv run ruff check .               # lint
uv run mypy                       # tipos
```

Si tu PostgreSQL de pruebas está en otro sitio, usa las variables `TEST_DB_HOST`,
`TEST_DB_PORT`, `TEST_ADMIN_DB_USER` y `TEST_ADMIN_DB_PASSWORD`.

Con `make` (macOS/Linux) tienes atajos: `make dev`, `make test`, `make lint`.

## 2.7. Comandos operativos

```bash
# Migrar todas las organizaciones activas a la última versión del esquema de tenant
uv run python scripts/migrate_tenants.py

# Reintentar la provisión de una organización que quedó en "failed"
uv run python scripts/provision_tenant.py <tenant_id>

# Prueba de humo completa contra cualquier URL
uv run python scripts/smoke_test.py --base-url http://localhost:8000 --mode full
```

## 2.8. Problemas comunes

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `connection refused` en el bootstrap | PostgreSQL no arrancó | `docker compose ps`, `docker compose logs db` |
| `Faltan credenciales para el usuario…` | No existe `.env` | `cp .env.example .env` |
| `JWT_SECRET debe tener al menos 32 caracteres` | Secreto corto | Genera uno con el comando de 2.2 |
| `/health/ready` da 503 | La API no llega a `control_db` | Ejecuta el bootstrap; revisa `DB_HOST`/`DB_PORT` |
| Puerto 5432 ocupado | Ya tienes otro PostgreSQL | Para el otro o cambia el puerto en `docker-compose.yml` y `DB_PORT` |
| Quiero empezar de cero | — | `docker compose down -v && rm -rf .local-secrets` y repite 2.3–2.4 |
