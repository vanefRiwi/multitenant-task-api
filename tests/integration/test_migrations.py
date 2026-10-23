from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.infrastructure.container import Container
from app.infrastructure.database.migrations import head_revision
from app.infrastructure.ops.bootstrap import bootstrap_control_plane
from app.infrastructure.ops.tenant_migrations import migrate_all_tenants
from tests.conftest import TEST_CONTROL_DB, admin_connect
from tests.helpers import create_tenant, new_user


def _tables(settings: Settings, database: str) -> set[str]:
    with admin_connect(settings, database) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {name for (name,) in rows}


def test_central_migrations_are_applied(settings: Settings) -> None:
    assert _tables(settings, TEST_CONTROL_DB) == {
        "users",
        "tenants",
        "memberships",
        "alembic_version_central",
    }
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        (version,) = conn.execute("SELECT version_num FROM alembic_version_central").fetchone() or (
            "",
        )
    assert version == head_revision("central")


def test_bootstrap_is_idempotent(settings: Settings, container: Container) -> None:
    first = bootstrap_control_plane(settings, container.secrets)
    second = bootstrap_control_plane(settings, container.secrets)
    assert first == second


def test_each_tenant_gets_its_own_migrated_database(client: TestClient, settings: Settings) -> None:
    _, headers = new_user(client)
    tenant = create_tenant(client, headers)
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        (database,) = conn.execute(
            "SELECT database_name FROM tenants WHERE id = %s", (tenant["id"],)
        ).fetchone() or ("",)
    assert database == "test_tenant_" + tenant["id"].replace("-", "")
    assert _tables(settings, database) == {"tasks", "alembic_version_tenant"}
    with admin_connect(settings, database) as conn:
        (version,) = conn.execute("SELECT version_num FROM alembic_version_tenant").fetchone() or (
            "",
        )
    assert version == head_revision("tenant")


def test_migrate_all_tenants_is_idempotent(
    client: TestClient, settings: Settings, container: Container
) -> None:
    _, headers = new_user(client)
    ids = {create_tenant(client, headers)["id"] for _ in range(2)}
    result = migrate_all_tenants(settings, container.secrets)
    assert result["failed"] == []
    assert {m["tenant_id"] for m in result["migrated"]} == ids
    assert all(m["revision"] == head_revision("tenant") for m in result["migrated"])
