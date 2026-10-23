from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.application.tenants.provision_tenant import ProvisionTenant
from app.config.settings import Settings
from app.infrastructure.database.central import create_central_engine
from app.infrastructure.database.credentials import central_credentials, provisioner_credentials
from app.infrastructure.database.unit_of_work import SqlModelUnitOfWork
from app.infrastructure.repositories.sqlmodel_tenant_repository import SqlModelTenantRepository
from app.infrastructure.secrets.secret_provider import SecretProvider
from app.infrastructure.tenancy.postgres_tenant_provisioner import PostgresTenantProvisioner


def retry_tenant_provisioning(
    settings: Settings, secrets: SecretProvider, tenant_id: UUID
) -> dict[str, Any]:
    """Reintenta la provisión de un tenant en estado 'failed' o 'provisioning'."""
    engine = create_central_engine(settings, central_credentials(settings, secrets))
    try:
        with Session(engine, expire_on_commit=False) as session:
            use_case = ProvisionTenant(
                SqlModelTenantRepository(session),
                PostgresTenantProvisioner(
                    settings, provisioner_credentials(settings, secrets), secrets
                ),
                SqlModelUnitOfWork(session),
            )
            tenant = use_case.retry(tenant_id)
            return {"tenant_id": str(tenant.id), "status": tenant.status.value}
    finally:
        engine.dispose()
