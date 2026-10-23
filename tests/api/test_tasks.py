from fastapi.testclient import TestClient

from tests.helpers import API, create_task, create_tenant, new_user


def _setup(client: TestClient) -> tuple[dict[str, str], str, str]:
    user, headers = new_user(client)
    tenant = create_tenant(client, headers)
    return headers, tenant["id"], user["id"]


def test_task_crud(client: TestClient) -> None:
    headers, tenant_id, user_id = _setup(client)
    base = f"{API}/tenants/{tenant_id}/tasks"

    # Crear
    response = client.post(
        base,
        json={
            "title": "Preparar demo",
            "description": "Slides y API",
            "priority": "high",
            "due_date": "2030-01-15T10:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 201
    task = response.json()
    assert task["status"] == "pending"
    assert task["priority"] == "high"
    assert task["created_by"] == user_id

    # Consultar
    response = client.get(f"{base}/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Preparar demo"

    # Actualizar parcialmente (PATCH)
    response = client.patch(
        f"{base}/{task['id']}", json={"status": "in_progress", "due_date": None}, headers=headers
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "in_progress"
    assert updated["due_date"] is None
    assert updated["title"] == "Preparar demo"  # no enviado => no cambia
    assert updated["updated_at"] >= task["updated_at"]

    # Listar
    response = client.get(base, headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1

    # Eliminar
    assert client.delete(f"{base}/{task['id']}", headers=headers).status_code == 204
    assert client.get(f"{base}/{task['id']}", headers=headers).status_code == 404
    assert client.delete(f"{base}/{task['id']}", headers=headers).status_code == 404


def test_pagination_with_limit_and_offset(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    for i in range(5):
        create_task(client, headers, tenant_id, title=f"Tarea {i}")

    base = f"{API}/tenants/{tenant_id}/tasks"
    page1 = client.get(base, params={"limit": 2, "offset": 0}, headers=headers).json()
    page3 = client.get(base, params={"limit": 2, "offset": 4}, headers=headers).json()
    assert page1["total"] == 5 and len(page1["items"]) == 2
    assert page1["limit"] == 2 and page1["offset"] == 0
    assert len(page3["items"]) == 1
    ids = {t["id"] for t in page1["items"]} | {t["id"] for t in page3["items"]}
    assert len(ids) == 3


def test_limit_above_configured_maximum_is_rejected(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    base = f"{API}/tenants/{tenant_id}/tasks"
    assert client.get(base, params={"limit": 51}, headers=headers).status_code == 400
    assert client.get(base, params={"limit": 0}, headers=headers).status_code == 422
    assert client.get(base, params={"offset": -1}, headers=headers).status_code == 422


def test_filter_by_status_and_priority(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    create_task(client, headers, tenant_id, title="a", status="completed", priority="low")
    create_task(client, headers, tenant_id, title="b", status="pending", priority="low")
    create_task(client, headers, tenant_id, title="c", status="completed", priority="high")

    base = f"{API}/tenants/{tenant_id}/tasks"
    body = client.get(base, params={"status": "completed"}, headers=headers).json()
    assert {t["title"] for t in body["items"]} == {"a", "c"}
    body = client.get(base, params={"status": "completed", "priority": "low"}, headers=headers)
    assert [t["title"] for t in body.json()["items"]] == ["a"]


def test_task_validation_errors(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    base = f"{API}/tenants/{tenant_id}/tasks"
    cases = [
        {"title": ""},
        {"title": "x" * 201},
        {"title": "ok", "status": "done"},
        {"title": "ok", "priority": "urgent"},
        {"title": "ok", "due_date": "2030-01-01T00:00:00"},  # sin zona horaria
        {"title": "ok", "created_by": "00000000-0000-0000-0000-000000000000"},
    ]
    for body in cases:
        response = client.post(base, json=body, headers=headers)
        assert response.status_code == 422, body


def test_patch_with_empty_body_returns_400(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    task = create_task(client, headers, tenant_id)
    response = client.patch(
        f"{API}/tenants/{tenant_id}/tasks/{task['id']}", json={}, headers=headers
    )
    assert response.status_code == 400


def test_patch_cannot_null_required_fields(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    task = create_task(client, headers, tenant_id)
    response = client.patch(
        f"{API}/tenants/{tenant_id}/tasks/{task['id']}", json={"title": None}, headers=headers
    )
    assert response.status_code == 400


def test_malformed_ids_return_422(client: TestClient) -> None:
    headers, tenant_id, _ = _setup(client)
    assert client.get(f"{API}/tenants/no-uuid/tasks", headers=headers).status_code == 422
    assert client.get(f"{API}/tenants/{tenant_id}/tasks/123", headers=headers).status_code == 422
