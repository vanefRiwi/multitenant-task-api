from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.config.settings import Settings
from tests.conftest import TEST_CONTROL_DB, admin_connect
from tests.helpers import API, new_user


def _token(settings: Settings, **overrides: object) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.jwt_issuer,
    }
    payload.update(overrides)
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, str(settings.jwt_secret), algorithm="HS256")


def _me(client: TestClient, token: str) -> int:
    return client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code


def test_expired_token_is_rejected(client: TestClient, settings: Settings) -> None:
    user, _ = new_user(client)
    past = datetime.now(UTC) - timedelta(hours=2)
    token = _token(settings, sub=user["id"], iat=past, exp=past + timedelta(minutes=5))
    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "El token ha expirado"


def test_tampered_or_foreign_tokens_are_rejected(client: TestClient, settings: Settings) -> None:
    user, headers = new_user(client)
    valid = headers["Authorization"].removeprefix("Bearer ")
    header, payload, signature = valid.split(".")
    bad_tokens = [
        "esto-no-es-un-jwt",
        f"{header}.{payload}.{signature[::-1]}",  # firma alterada
        jwt.encode(
            {"sub": user["id"], "iss": settings.jwt_issuer, "exp": 9999999999, "iat": 1},
            "otro-secreto-que-tambien-tiene-mas-de-32-chars",
            algorithm="HS256",
        ),
        _token(settings, sub=user["id"], iss="otro-emisor"),
        _token(settings, sub=user["id"], iss=None),  # sin emisor
        _token(settings, sub=None),  # sin sub
        _token(settings, sub="no-es-un-uuid"),
        _token(settings, sub=user["id"], exp=None),  # sin expiración
        # alg "none": token sin firma
        jwt.encode({"sub": user["id"], "iss": settings.jwt_issuer}, None, algorithm="none"),
    ]
    for token in bad_tokens:
        assert _me(client, token) == 401, token


def test_token_of_unknown_or_inactive_user_is_rejected(
    client: TestClient, settings: Settings
) -> None:
    assert _me(client, _token(settings)) == 401  # usuario que no existe

    user, headers = new_user(client)
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        conn.execute("UPDATE users SET is_active = false WHERE id = %s", (user["id"],))
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_non_bearer_scheme_is_rejected(client: TestClient) -> None:
    _, headers = new_user(client)
    token = headers["Authorization"].removeprefix("Bearer ")
    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 401


def test_passwords_are_stored_with_argon2(client: TestClient, settings: Settings) -> None:
    user, _ = new_user(client)
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
        (password_hash,) = row.fetchone() or ("",)
    assert password_hash.startswith("$argon2id$")
