"""El corazón del multitenant: un usuario NUNCA ve ni toca datos de otra organización."""

from fastapi.testclient import TestClient

from app.config.settings import Settings
from tests.conftest import TEST_CONTROL_DB, admin_connect
from tests.helpers import API, create_task, create_tenant, new_user


def test_user_cannot_access_foreign_tenant(client: TestClient) -> None:
    _, ana = new_user(client, "ana")
    _, beto = new_user(client, "beto")
    acme = create_tenant(client, ana, "acme")
    task = create_task(client, ana, acme["id"], title="Secreto de Acme")

    base = f"{API}/tenants/{acme['id']}"
    attempts = [
        client.get(base, headers=beto),
        client.get(f"{base}/tasks", headers=beto),
        client.get(f"{base}/tasks/{task['id']}", headers=beto),
        client.post(f"{base}/tasks", json={"title": "intruso"}, headers=beto),
        client.patch(f"{base}/tasks/{task['id']}", json={"title": "hackeado"}, headers=beto),
        client.delete(f"{base}/tasks/{task['id']}", headers=beto),
        client.get(f"{base}/members", headers=beto),
        client.post(f"{base}/members", json={"email": "x@example.com"}, headers=beto),
    ]
    for response in attempts:
        # 404 y no 403: el intruso no puede saber siquiera que la organización existe.
        assert response.status_code == 404, response.request.url
        assert response.json()["error"]["code"] == "tenant_not_found"
        assert "Secreto de Acme" not in response.text

    # La tarea sigue intacta para su dueña.
    response = client.get(f"{base}/tasks/{task['id']}", headers=ana)
    assert response.json()["title"] == "Secreto de Acme"


def test_task_ids_do_not_cross_tenants(client: TestClient) -> None:
    """Aunque Ana pertenezca a dos organizaciones, una tarea de A no existe en B."""
    _, ana = new_user(client, "ana")
    org_a = create_tenant(client, ana, "org-a")
    org_b = create_tenant(client, ana, "org-b")
    task_a = create_task(client, ana, org_a["id"], title="Solo en A")
    create_task(client, ana, org_b["id"], title="Solo en B")

    response = client.get(f"{API}/tenants/{org_b['id']}/tasks/{task_a['id']}", headers=ana)
    assert response.status_code == 404
    titles_b = [
        t["title"]
        for t in client.get(f"{API}/tenants/{org_b['id']}/tasks", headers=ana).json()["items"]
    ]
    titles_a = [
        t["title"]
        for t in client.get(f"{API}/tenants/{org_a['id']}/tasks", headers=ana).json()["items"]
    ]
    assert titles_a == ["Solo en A"]
    assert titles_b == ["Solo en B"]


def test_inactive_tenant_is_blocked(client: TestClient, settings: Settings) -> None:
    _, ana = new_user(client)
    tenant = create_tenant(client, ana)
    create_task(client, ana, tenant["id"])

    for status in ("suspended", "provisioning", "failed"):
        with admin_connect(settings, TEST_CONTROL_DB) as conn:
            conn.execute("UPDATE tenants SET status = %s WHERE id = %s", (status, tenant["id"]))
        response = client.get(f"{API}/tenants/{tenant['id']}/tasks", headers=ana)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "tenant_not_active"
        # La organización sigue visible (con su estado) para sus miembros.
        assert client.get(f"{API}/tenants/{tenant['id']}", headers=ana).json()["status"] == status


def test_revoked_membership_loses_access_immediately(client: TestClient) -> None:
    _, owner = new_user(client, "owner")
    member_user, member = new_user(client, "member")
    tenant = create_tenant(client, owner)
    url = f"{API}/tenants/{tenant['id']}"
    client.post(f"{url}/members", json={"email": member_user["email"]}, headers=owner)
    assert client.get(f"{url}/tasks", headers=member).status_code == 200

    response = client.delete(f"{url}/members/{member_user['id']}", headers=owner)
    assert response.status_code == 204

    # Mismo JWT, todavía no expirado: ya no autoriza nada en esa organización.
    assert client.get(f"{url}/tasks", headers=member).status_code == 404
    assert client.get(f"{API}/tenants", headers=member).json() == []


def test_member_cannot_manage_memberships(client: TestClient) -> None:
    owner_user, owner = new_user(client, "owner")
    member_user, member = new_user(client, "member")
    other_user, _ = new_user(client, "other")
    tenant = create_tenant(client, owner)
    url = f"{API}/tenants/{tenant['id']}/members"
    client.post(url, json={"email": member_user["email"]}, headers=owner)

    response = client.post(url, json={"email": other_user["email"]}, headers=member)
    assert response.status_code == 403
    assert (
        client.patch(
            f"{url}/{member_user['id']}", json={"role": "owner"}, headers=member
        ).status_code
        == 403
    )
    assert client.delete(f"{url}/{owner_user['id']}", headers=member).status_code == 403
    # Pero sí puede salir por sí mismo.
    assert client.delete(f"{url}/{member_user['id']}", headers=member).status_code == 204


def test_client_cannot_choose_database_name(client: TestClient) -> None:
    _, ana = new_user(client)
    response = client.post(
        f"{API}/tenants",
        json={"name": "Mala", "slug": "mala", "database_name": "control_db"},
        headers=ana,
    )
    assert response.status_code == 422
    response = client.post(
        f"{API}/tenants",
        json={"name": "Mala", "slug": "mala", "secret_arn": "arn:aws:secretsmanager:x"},
        headers=ana,
    )
    assert response.status_code == 422
