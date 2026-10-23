"""Los errores tienen formato uniforme y no filtran información sensible."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.infrastructure.container import Container
from app.main import create_app
from tests.conftest import TEST_CONTROL_DB, admin_connect, make_settings
from tests.helpers import API, PASSWORD, create_task, create_tenant, new_user

SENSITIVE = ["password", "secret", "Traceback", "SELECT ", "postgresql", "psycopg", "test_tenant_"]


def _assert_clean(text: str) -> None:
    for word in SENSITIVE:
        assert word not in text, f"La respuesta filtra '{word}': {text}"


def test_validation_errors_do_not_echo_submitted_values(client: TestClient) -> None:
    secret_value = "mi-clave-ultrasecreta-de-prueba" * 10  # > 128 caracteres
    response = client.post(
        f"{API}/auth/register", json={"email": "a@example.com", "password": secret_value}
    )
    assert response.status_code == 422
    assert secret_value not in response.text
    assert set(response.json()) == {"error"}


def test_unhandled_errors_return_generic_500(
    settings: Settings, container: Container, caplog: pytest.LogCaptureFixture
) -> None:
    app: FastAPI = create_app(settings, container)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("password=super-secreta host=db.interno")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "super-secreta" not in response.text and "db.interno" not in response.text
    assert "super-secreta" not in caplog.text


def test_responses_never_expose_internal_connection_data(client: TestClient) -> None:
    _, headers = new_user(client)
    tenant = create_tenant(client, headers)
    create_task(client, headers, tenant["id"])
    for url in [
        f"{API}/tenants",
        f"{API}/tenants/{tenant['id']}",
        f"{API}/tenants/{tenant['id']}/tasks",
        f"{API}/tenants/{tenant['id']}/members",
    ]:
        _assert_clean(client.get(url, headers=headers).text)


def test_database_down_returns_503_without_details(
    secrets_dir: object, caplog: pytest.LogCaptureFixture
) -> None:
    # Puerto donde no hay PostgreSQL: simula una caída de la base de datos.
    broken = make_settings(secrets_dir, db_port=1, db_connect_timeout_seconds=1)  # type: ignore[arg-type]
    with TestClient(create_app(broken)) as client:
        responses = [
            client.get("/health/ready"),
            client.post(
                f"{API}/auth/register", json={"email": "a@example.com", "password": PASSWORD}
            ),
        ]
    for response in responses:
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_unavailable"
        _assert_clean(response.text)
    assert PASSWORD not in caplog.text
    assert "test-central-password" not in caplog.text


def test_tenant_database_unreachable_returns_503(
    client: TestClient, settings: Settings, container: Container
) -> None:
    _, headers = new_user(client)
    tenant = create_tenant(client, headers)
    # El secreto del tenant desaparece (p. ej. borrado por error): la API no se cae.
    with admin_connect(settings, TEST_CONTROL_DB) as conn:
        conn.execute(
            "UPDATE tenants SET secret_arn = 'local:test/tenants/no-existe' WHERE id = %s",
            (tenant["id"],),
        )
    response = client.get(f"{API}/tenants/{tenant['id']}/tasks", headers=headers)
    assert response.status_code == 503
    _assert_clean(response.text)


def test_logs_do_not_contain_passwords_or_tokens(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    _, headers = new_user(client)
    create_tenant(client, headers)
    token = headers["Authorization"].removeprefix("Bearer ")
    assert PASSWORD not in caplog.text
    assert token not in caplog.text
    assert "test-provisioner-password" not in caplog.text
