import logging
from typing import Any

from sqlmodel import Session

from app.config.settings import Settings
from app.domain.enums import TenantStatus
from app.infrastructure.database.central import create_central_engine
from app.infrastructure.database.credentials import central_credentials, provisioner_credentials
from app.infrastructure.repositories.sqlmodel_tenant_repository import SqlModelTenantRepository
from app.infrastructure.secrets.secret_provider import SecretProvider
from app.infrastructure.tenancy.postgres_tenant_provisioner import PostgresTenantProvisioner

logger = logging.getLogger(__name__)


def migrate_all_tenants(settings: Settings, secrets: SecretProvider) -> dict[str, Any]:
    """Aplica las migraciones de tenant a cada organización activa.

    Un fallo en un tenant no detiene a los demás; se registra y se devuelve en el
    resumen para que el pipeline falle de forma visible."""
    engine = create_central_engine(settings, central_credentials(settings, secrets))
    try:
        with Session(engine) as session:
            tenants = SqlModelTenantRepository(session).list_all()
    finally:
        engine.dispose()

    provisioner = PostgresTenantProvisioner(
        settings, provisioner_credentials(settings, secrets), secrets
    )
    migrated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for tenant in tenants:
        if tenant.status != TenantStatus.ACTIVE:
            continue
        try:
            revision = provisioner.migrate(tenant.database_name)
            migrated.append({"tenant_id": str(tenant.id), "revision": revision})
        except Exception as exc:
            logger.error("Migración fallida en tenant %s (%s)", tenant.id, type(exc).__name__)
            failed.append({"tenant_id": str(tenant.id), "error": type(exc).__name__})
    return {"migrated": migrated, "failed": failed}
