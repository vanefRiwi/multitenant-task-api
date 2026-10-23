from fastapi.testclient import TestClient

from tests.helpers import API, create_tenant, new_user


def test_create_tenant_returns_201_and_creator_is_owner(client: TestClient) -> None:
    _, headers = new_user(client)
    response = client.post(
        f"{API}/tenants", json={"name": "Acme Corp", "slug": "acme-corp"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert body["role"] == "owner"
    assert body["slug"] == "acme-corp"
    # Los datos internos de conexión nunca salen por la API.
    assert "database_name" not in body and "secret_arn" not in body


def test_list_tenants_only_returns_authorized_ones(client: TestClient) -> None:
    _, ana = new_user(client, "ana")
    _, beto = new_user(client, "beto")
    acme = create_tenant(client, ana, "acme")
    create_tenant(client, beto, "globex")

    response = client.get(f"{API}/tenants", headers=ana)
    assert response.status_code == 200
    assert [t["id"] for t in response.json()] == [acme["id"]]


def test_get_tenant(client: TestClient) -> None:
    _, headers = new_user(client)
    tenant = create_tenant(client, headers)
    response = client.get(f"{API}/tenants/{tenant['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == tenant["id"]


def test_duplicate_slug_returns_409(client: TestClient) -> None:
    _, headers = new_user(client)
    create_tenant(client, headers, "same-slug")
    response = client.post(
        f"{API}/tenants", json={"name": "Otra", "slug": "same-slug"}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tenant_slug_already_exists"


def test_invalid_slug_returns_422(client: TestClient) -> None:
    _, headers = new_user(client)
    response = client.post(
        f"{API}/tenants", json={"name": "Mala", "slug": "Con Espacios!"}, headers=headers
    )
    assert response.status_code == 422


def test_unknown_tenant_returns_404(client: TestClient) -> None:
    _, headers = new_user(client)
    response = client.get(f"{API}/tenants/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 404


def test_tenant_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/tenants").status_code == 401
    assert client.post(f"{API}/tenants", json={"name": "x", "slug": "xyz"}).status_code == 401
