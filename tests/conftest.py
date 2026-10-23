"""Fixtures comunes. Las pruebas usan un PostgreSQL REAL (nunca el de producción).

Variables (con valores por defecto para el docker-compose local y el servicio de CI):
    TEST_DB_HOST=localhost  TEST_DB_PORT=5432
    TEST_ADMIN_DB_USER=postgres  TEST_ADMIN_DB_PASSWORD=postgres

Todo lo que crean las pruebas lleva el prefijo `test_` (control_db de prueba, bases y
roles de tenants) y se borra al empezar y al terminar la sesión de pruebas.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql

from app.config.settings import Settings
from app.infrastructure.container import Container, build_container
from app.infrastructure.ops.bootstrap import bootstrap_control_plane
from app.infrastructure.secrets.secret_provider import LocalFileSecretProvider
from app.main import create_app

TEST_PREFIX = "test_tenant_"
TEST_CONTROL_DB = "test_control_db"


def make_settings(secrets_dir: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "log_level": "INFO",
        "db_host": os.getenv("TEST_DB_HOST", "localhost"),
        "db_port": int(os.getenv("TEST_DB_PORT", "5432")),
        "control_db_name": TEST_CONTROL_DB,
        "admin_db_user": os.getenv("TEST_ADMIN_DB_USER", "postgres"),
        "admin_db_password": os.getenv("TEST_ADMIN_DB_PASSWORD", "postgres"),
        "central_db_user": "test_app_central",
        "central_db_password": "test-central-password",
        "provisioner_db_user": "test_tenant_provisioner",
        "provisioner_db_password": "test-provisioner-password",
        "tenant_db_prefix": TEST_PREFIX,
        "secret_provider": "local",
        "local_secrets_dir": str(secrets_dir),
        "tenant_secret_prefix": "test",
        "jwt_secret": "test-jwt-secret-que-tiene-mas-de-32-caracteres",
        "jwt_issuer": "multitenant-task-api-test",
        "pagination_max_limit": 50,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def admin_connect(settings: Settings, database: str = "postgres") -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.admin_db_user,
        password=settings.admin_db_password,
        dbname=database,
        autocommit=True,
    )


def drop_test_objects(settings: Settings) -> None:
    with admin_connect(settings) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT datname FROM pg_database WHERE datname = %s OR datname LIKE %s",
            (TEST_CONTROL_DB, TEST_PREFIX + "%"),
        )
        for (name,) in cur.fetchall():
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
        cur.execute(
            "SELECT rolname FROM pg_roles WHERE rolname LIKE %s OR rolname IN (%s, %s)",
            (TEST_PREFIX + "%", settings.central_db_user, settings.provisioner_db_user),
        )
        roles = [name for (name,) in cur.fetchall()]
        # Primero los roles de tenant (los creó el provisionador) y después el resto.
        roles.sort(key=lambda role: not role.startswith(TEST_PREFIX))
        for name in roles:
            cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def secrets_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("secrets")


@pytest.fixture(scope="session")
def settings(secrets_dir: Path) -> Iterator[Settings]:
    settings = make_settings(secrets_dir)
    try:
        drop_test_objects(settings)
    except psycopg.OperationalError as exc:
        pytest.exit(f"PostgreSQL de pruebas no disponible: {exc}", returncode=2)
    bootstrap_control_plane(settings, LocalFileSecretProvider(secrets_dir))
    yield settings
    drop_test_objects(settings)


@pytest.fixture(scope="session")
def container(settings: Settings) -> Iterator[Container]:
    container = build_container(settings)
    yield container
    container.close()


@pytest.fixture(autouse=True)
def clean_control_db(request: pytest.FixtureRequest) -> None:
    """Vacía control_db antes de cada prueba que lo use."""
    if "settings" not in request.fixturenames:
        return
    settings: Settings = request.getfixturevalue("settings")
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        conn.execute("TRUNCATE memberships, tenants, users CASCADE")


@pytest.fixture
def app(settings: Settings, container: Container) -> FastAPI:
    return create_app(settings, container)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
