"""Permisos mínimos en PostgreSQL: aunque alguien robara la contraseña de un tenant,
no podría entrar en la base de otro tenant ni en control_db, ni cambiar el esquema."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.infrastructure.container import Container
from tests.conftest import TEST_CONTROL_DB, admin_connect
from tests.helpers import create_tenant, new_user


def _tenant_credentials(container: Container, settings: Settings, tenant_id: str) -> dict[str, str]:
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        row = conn.execute("SELECT secret_arn FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
    assert row is not None
    return container.secrets.get_json(row[0])


def _connect(settings: Settings, user: str, password: str, database: str) -> psycopg.Connection:
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=user,
        password=password,
        dbname=database,
        autocommit=True,
        connect_timeout=5,
    )


def test_tenant_role_is_confined_to_its_database(
    client: TestClient, settings: Settings, container: Container
) -> None:
    _, ana = new_user(client)
    tenant_a = create_tenant(client, ana)
    tenant_b = create_tenant(client, ana)
    creds_a = _tenant_credentials(container, settings, tenant_a["id"])
    creds_b = _tenant_credentials(container, settings, tenant_b["id"])
    assert creds_a["dbname"] != creds_b["dbname"]

    # Puede entrar en SU base y trabajar con filas.
    with _connect(settings, creds_a["username"], creds_a["password"], creds_a["dbname"]) as conn:
        conn.execute("SELECT count(*) FROM tasks")
        # ...pero no puede cambiar el esquema ni tocar la tabla de versiones de Alembic.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE hack (id int)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DROP TABLE tasks")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM alembic_version_tenant")

    # No puede conectarse a la base de otro tenant ni a control_db.
    for database in (creds_b["dbname"], TEST_CONTROL_DB):
        with pytest.raises(psycopg.OperationalError) as exc_info:
            _connect(settings, creds_a["username"], creds_a["password"], database)
        assert "permission denied" in str(exc_info.value)


def test_central_app_role_cannot_create_databases_or_tables(settings: Settings) -> None:
    password = str(settings.central_db_password)
    with _connect(settings, settings.central_db_user, password, TEST_CONTROL_DB) as conn:
        conn.execute("SELECT count(*) FROM users")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE DATABASE hack")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE hack (id int)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DROP TABLE users")


def test_provisioner_is_not_superuser(settings: Settings) -> None:
    with admin_connect(settings) as conn:
        row = conn.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = %s",
            (settings.provisioner_db_user,),
        ).fetchone()
    assert row == (False, True, True)
