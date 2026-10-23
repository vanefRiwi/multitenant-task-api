"""Gestión de conexiones por tenant: sesiones aisladas, caché limitada y con caducidad."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

from app.config.settings import Settings
from app.domain.entities.tenant import Tenant
from app.domain.enums import TenantStatus
from app.domain.exceptions import ServiceUnavailableError, TenantNotActiveError
from app.infrastructure.container import Container
from app.infrastructure.repositories.sqlmodel_tenant_repository import SqlModelTenantRepository
from app.infrastructure.tenancy.tenant_database_factory import TenantDatabaseFactory
from tests.conftest import make_settings
from tests.helpers import create_tenant, new_user


def _tenants(client: TestClient, container: Container, count: int) -> list[Tenant]:
    _, headers = new_user(client)
    ids = [UUID(create_tenant(client, headers)["id"]) for _ in range(count)]
    with Session(container.central_engine) as session:
        repo = SqlModelTenantRepository(session)
        return [t for t in (repo.get_by_id(i) for i in ids) if t is not None]


def _current_database(factory: TenantDatabaseFactory, tenant: Tenant) -> str:
    sessions = factory.session(tenant)
    session = next(sessions)
    try:
        return str(session.exec(text("SELECT current_database()")).one()[0])  # type: ignore[call-overload]
    finally:
        sessions.close()


def test_each_session_points_to_its_own_tenant_database(
    client: TestClient, container: Container
) -> None:
    tenant_a, tenant_b = _tenants(client, container, 2)
    factory = container.tenant_databases
    assert _current_database(factory, tenant_a) == tenant_a.database_name
    assert _current_database(factory, tenant_b) == tenant_b.database_name
    # Intercalar peticiones no mezcla las conexiones.
    assert _current_database(factory, tenant_a) == tenant_a.database_name


def test_engine_cache_is_bounded_and_expires(
    client: TestClient, container: Container, secrets_dir: object
) -> None:
    tenants = _tenants(client, container, 3)
    now = [0.0]
    settings: Settings = make_settings(
        secrets_dir,  # type: ignore[arg-type]
        tenant_engine_cache_size=2,
        tenant_engine_ttl_seconds=60,
    )
    factory = TenantDatabaseFactory(settings, container.secrets, clock=lambda: now[0])

    engines = [factory.get_engine(t) for t in tenants]
    assert factory.cached_tenants == [tenants[1].id, tenants[2].id]  # el más antiguo salió
    assert factory.get_engine(tenants[2]) is engines[2]  # reutiliza

    now[0] = 61.0  # caduca
    assert factory.get_engine(tenants[2]) is not engines[2]
    factory.dispose_all()
    assert factory.cached_tenants == []


def test_factory_refuses_inactive_tenants(container: Container) -> None:
    tenant = Tenant(name="x", slug="x", database_name="test_tenant_x", secret_arn="local:x")
    tenant.status = TenantStatus.SUSPENDED
    with pytest.raises(TenantNotActiveError):
        container.tenant_databases.get_engine(tenant)


def test_factory_refuses_secret_of_another_tenant(client: TestClient, container: Container) -> None:
    tenant_a, tenant_b = _tenants(client, container, 2)
    # Registro manipulado: el tenant B apunta al secreto del tenant A.
    forged = Tenant(
        id=tenant_b.id,
        name=tenant_b.name,
        slug=tenant_b.slug,
        database_name=tenant_b.database_name,
        status=TenantStatus.ACTIVE,
        secret_arn=tenant_a.secret_arn,
    )
    factory = TenantDatabaseFactory(container.settings, container.secrets)
    with pytest.raises(ServiceUnavailableError):
        factory.get_engine(forged)
