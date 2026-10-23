from uuid import uuid4

from app.application.tenants.provision_tenant import ProvisionTenant
from app.domain.entities.tenant import Membership, Tenant, TenantAccess, build_database_name
from app.domain.entities.user import User
from app.domain.enums import MembershipRole, TenantStatus
from app.domain.exceptions import TenantSlugAlreadyExistsError
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.repositories.membership_repository import MembershipRepository
from app.domain.repositories.tenant_repository import TenantRepository


class CreateTenant:
    def __init__(
        self,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        provision: ProvisionTenant,
        uow: UnitOfWork,
        database_prefix: str,
    ) -> None:
        self._tenants = tenants
        self._memberships = memberships
        self._provision = provision
        self._uow = uow
        self._database_prefix = database_prefix

    def execute(self, owner: User, name: str, slug: str) -> TenantAccess:
        # 1. Registrar el tenant en estado 'provisioning'. El nombre de la BD lo
        #    genera el sistema a partir del id; el cliente no puede elegirlo.
        tenant_id = uuid4()
        tenant = Tenant(
            id=tenant_id,
            name=name,
            slug=slug,
            database_name=build_database_name(self._database_prefix, tenant_id),
            status=TenantStatus.PROVISIONING,
        )
        if self._tenants.get_by_slug(tenant.slug) is not None:
            raise TenantSlugAlreadyExistsError()
        self._tenants.add(tenant)

        # 2. Membresía del creador como owner.
        self._memberships.add(
            Membership(user_id=owner.id, tenant_id=tenant.id, role=MembershipRole.OWNER)
        )
        # Se confirma ya: si la provisión falla, el tenant queda registrado como
        # 'failed' y se puede reintentar sin perder la organización.
        self._uow.commit()

        # 3-6. Crear BD, credenciales, secreto, migraciones y pasar a 'active'.
        self._provision.execute(tenant)
        return TenantAccess(tenant=tenant, role=MembershipRole.OWNER)
