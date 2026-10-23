from fastapi.testclient import TestClient

from tests.helpers import API, create_task, create_tenant, new_user


def test_owner_adds_member_who_can_work_with_tasks(client: TestClient) -> None:
    _, owner = new_user(client, "owner")
    member_user, member = new_user(client, "member")
    tenant = create_tenant(client, owner)
    members_url = f"{API}/tenants/{tenant['id']}/members"

    response = client.post(members_url, json={"email": member_user["email"]}, headers=owner)
    assert response.status_code == 201
    assert response.json()["role"] == "member"

    listed = client.get(members_url, headers=member).json()
    assert {m["role"] for m in listed} == {"owner", "member"}

    # El miembro ve la organización y puede crear y leer tareas.
    assert [t["role"] for t in client.get(f"{API}/tenants", headers=member).json()] == ["member"]
    task = create_task(client, member, tenant["id"], title="Del miembro")
    response = client.get(f"{API}/tenants/{tenant['id']}/tasks/{task['id']}", headers=owner)
    assert response.status_code == 200


def test_add_member_errors(client: TestClient) -> None:
    _, owner = new_user(client, "owner")
    member_user, _ = new_user(client, "member")
    tenant = create_tenant(client, owner)
    url = f"{API}/tenants/{tenant['id']}/members"

    assert client.post(url, json={"email": "nadie@example.com"}, headers=owner).status_code == 404
    assert client.post(url, json={"email": member_user["email"]}, headers=owner).status_code == 201
    response = client.post(url, json={"email": member_user["email"]}, headers=owner)
    assert response.status_code == 409
    response = client.post(url, json={"email": "x@example.com", "role": "admin"}, headers=owner)
    assert response.status_code == 422


def test_change_role_and_last_owner_protection(client: TestClient) -> None:
    owner_user, owner = new_user(client, "owner")
    member_user, member = new_user(client, "member")
    tenant = create_tenant(client, owner)
    url = f"{API}/tenants/{tenant['id']}/members"
    client.post(url, json={"email": member_user["email"]}, headers=owner)

    # No se puede dejar la organización sin owner.
    response = client.patch(f"{url}/{owner_user['id']}", json={"role": "member"}, headers=owner)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_owner"

    response = client.patch(f"{url}/{member_user['id']}", json={"role": "owner"}, headers=owner)
    assert response.status_code == 200
    assert response.json()["role"] == "owner"

    # Ahora hay dos owners: el primero ya puede bajar a member.
    response = client.patch(f"{url}/{owner_user['id']}", json={"role": "member"}, headers=member)
    assert response.status_code == 200
