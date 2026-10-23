import logging
from uuid import UUID

from app.domain.entities.tenant import Tenant
from app.domain.enums import TenantStatus
from app.domain.exceptions import (
    TenantNotFoundError,
    TenantProvisioningError,
)
from app.domain.ports.tenant_provisioner import TenantProvisioner
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.repositories.tenant_repository import TenantRepository

logger = logging.getLogger(__name__)


class ProvisionTenant:
    """Pasos 3 a 6 del flujo de creación: BD, credenciales, migraciones y 'active'.

    Se usa al crear la organización y también para reintentar una provisión fallida
    (scripts/provision_tenant.py)."""

    def __init__(
        self, tenants: TenantRepository, provisioner: TenantProvisioner, uow: UnitOfWork
    ) -> None:
        self._tenants = tenants
        self._provisioner = provisioner
        self._uow = uow

    def execute(self, tenant: Tenant) -> Tenant:
        try:
            secret_arn = self._provisioner.provision(tenant)
        except Exception as exc:
            logger.error("Provisión fallida para tenant %s (%s)", tenant.id, type(exc).__name__)
            self._uow.rollback()
            tenant.mark_failed()
            self._tenants.update(tenant)
            self._uow.commit()
            raise TenantProvisioningError() from exc

        tenant.mark_active(secret_arn)
        self._tenants.update(tenant)
        self._uow.commit()
        logger.info("Tenant %s aprovisionado", tenant.id)
        return tenant

    def retry(self, tenant_id: UUID) -> Tenant:
        tenant = self._tenants.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError()
        if tenant.status == TenantStatus.SUSPENDED:
            raise TenantProvisioningError("Un tenant suspendido no se reaprovisiona")
        return self.execute(tenant)
