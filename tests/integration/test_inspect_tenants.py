"""La acción de operaciones inspect_tenants muestra una base por tenant, sin secretos."""

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.infrastructure.container import Container
from app.infrastructure.ops.inspect_tenants import inspect_tenants
from tests.helpers import create_task, create_tenant, new_user


def test_inspect_tenants_reports_one_database_per_tenant(
    client: TestClient, settings: Settings, container: Container
) -> None:
    _, ana = new_user(client, "ana")
    _, beto = new_user(client, "beto")
    acme = create_tenant(client, ana)
    globex = create_tenant(client, beto)
    create_task(client, ana, acme["id"], title="Plan de Acme")

    report = inspect_tenants(settings, container.secrets)

    by_slug = {t["slug"]: t for t in report["tenants_en_control_db"]}
    acme_db, globex_db = by_slug[acme["slug"]], by_slug[globex["slug"]]
    assert acme_db["database_name"] != globex_db["database_name"]
    for entry in (acme_db, globex_db):
        assert entry["base_existe"] is True
        assert entry["database_name"] in report["bases_de_datos_en_rds"]
        assert entry["conectado_como"] == entry["database_name"]
    assert acme_db["titulos"] == ["Plan de Acme"] and acme_db["tareas"] == 1
    assert globex_db["tareas"] == 0
    assert report["prueba_cruzada"]["resultado"] == "acceso denegado por PostgreSQL"
    assert "password" not in str(report)
