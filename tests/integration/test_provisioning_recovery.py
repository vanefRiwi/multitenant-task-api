"""Si la provisión falla, el tenant queda 'failed', no opera tareas y se puede reintentar."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.infrastructure.container import Container
from app.infrastructure.ops.provisioning import retry_tenant_provisioning
from tests.helpers import API, create_task, new_user


def test_failed_provisioning_can_be_retried(
    client: TestClient,
    settings: Settings,
    container: Container,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, headers = new_user(client)

    def broken_migrate(database: str) -> None:
        raise RuntimeError("fallo simulado de migración")

    with monkeypatch.context() as patch:
        patch.setattr(container.provisioner, "migrate", broken_migrate)
        response = client.post(
            f"{API}/tenants", json={"name": "Frágil", "slug": "fragil"}, headers=headers
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "tenant_provisioning_failed"
    assert "fallo simulado" not in response.text

    [tenant] = client.get(f"{API}/tenants", headers=headers).json()
    assert tenant["status"] == "failed" and tenant["role"] == "owner"
    tasks_url = f"{API}/tenants/{tenant['id']}/tasks"
    assert client.get(tasks_url, headers=headers).status_code == 409

    # Reintento (lo mismo que hace scripts/provision_tenant.py): idempotente.
    result = retry_tenant_provisioning(settings, container.secrets, UUID(tenant["id"]))
    assert result["status"] == "active"
    create_task(client, headers, tenant["id"], title="Ya funciona")
    assert client.get(tasks_url, headers=headers).json()["total"] == 1


def test_secret_store_failure_marks_tenant_failed(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, headers = new_user(client)

    def broken_put(*args: object, **kwargs: object) -> str:
        raise ConnectionError("Secrets Manager caído")

    monkeypatch.setattr(container.provisioner._secrets, "put_json", broken_put)
    response = client.post(
        f"{API}/tenants", json={"name": "S", "slug": "sin-secreto"}, headers=headers
    )
    assert response.status_code == 503
    [tenant] = client.get(f"{API}/tenants", headers=headers).json()
    assert tenant["status"] == "failed"
