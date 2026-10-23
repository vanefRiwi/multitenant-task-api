import jwt
from fastapi.testclient import TestClient

from app.config.settings import Settings
from tests.helpers import API, PASSWORD, login, register


def test_register_returns_201_without_password_hash(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/register", json={"email": "Ana@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"  # normalizado
    assert body["is_active"] is True
    assert "password" not in response.text and "password_hash" not in body


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    register(client, "dup@example.com")
    response = client.post(
        f"{API}/auth/register", json={"email": "DUP@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"


def test_register_validates_email_and_password(client: TestClient) -> None:
    response = client.post(f"{API}/auth/register", json={"email": "no-es-email", "password": "x"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    fields = {tuple(d["loc"]) for d in error["details"]}
    assert ("body", "email") in fields and ("body", "password") in fields


def test_register_cannot_grant_global_privileges(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/register",
        json={"email": "admin@example.com", "password": PASSWORD, "is_admin": True},
    )
    assert response.status_code == 422


def test_login_returns_jwt_with_required_claims(client: TestClient, settings: Settings) -> None:
    user = register(client, "login@example.com")
    response = client.post(
        f"{API}/auth/login", json={"email": "login@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    claims = jwt.decode(
        body["access_token"],
        settings.jwt_secret,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
    )
    assert claims["sub"] == user["id"]
    assert {"sub", "exp", "iat", "iss"} <= claims.keys()


def test_login_with_wrong_password_or_unknown_email_returns_401(client: TestClient) -> None:
    register(client, "wrong@example.com")
    for email, password in [
        ("wrong@example.com", "otra-clave-123"),
        ("nadie@example.com", PASSWORD),
    ]:
        response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        # Mismo mensaje en ambos casos: no revela qué emails existen.
        assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_returns_authenticated_user(client: TestClient) -> None:
    user = register(client, "me@example.com")
    response = client.get(f"{API}/auth/me", headers=login(client, "me@example.com"))
    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "not_authenticated"


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_openapi_is_published(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/tenants/{tenant_id}/tasks" in schema["paths"]
