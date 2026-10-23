import itertools
from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"
PASSWORD = "contraseña-segura-123"
_counter = itertools.count()


def register(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, Any]:
    response = client.post(f"{API}/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def new_user(client: TestClient, name: str = "user") -> tuple[dict[str, Any], dict[str, str]]:
    email = f"{name}{next(_counter)}@example.com"
    user = register(client, email)
    return user, login(client, email)


def create_tenant(
    client: TestClient, headers: dict[str, str], slug: str | None = None
) -> dict[str, Any]:
    slug = slug or f"org-{next(_counter)}"
    response = client.post(
        f"{API}/tenants", json={"name": f"Org {slug}", "slug": slug}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_task(
    client: TestClient, headers: dict[str, str], tenant_id: str, **fields: Any
) -> dict[str, Any]:
    body = {"title": "Tarea", **fields}
    response = client.post(f"{API}/tenants/{tenant_id}/tasks", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
