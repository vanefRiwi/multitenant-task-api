from uuid import UUID

from app.domain.entities.tenant import TenantAccess
from app.domain.exceptions import TenantNotActiveError, TenantNotFoundError
from app.domain.repositories.membership_repository import MembershipRepository
from app.domain.repositories.tenant_repository import TenantRepository


class ResolveTenant:
    """Autorización central: ¿existe el tenant?, ¿el usuario es miembro?, ¿está activo?

    Se ejecuta en CADA petición a /tenants/{tenant_id}/... antes de abrir la base de
    datos del tenant. No confiamos en el tenant_id del cliente: lo validamos aquí."""

    def __init__(self, tenants: TenantRepository, memberships: MembershipRepository) -> None:
        self._tenants = tenants
        self._memberships = memberships

    def execute(self, user_id: UUID, tenant_id: UUID, *, require_active: bool) -> TenantAccess:
        tenant = self._tenants.get_by_id(tenant_id)
        membership = self._memberships.get(user_id, tenant_id) if tenant else None
        if tenant is None or membership is None:
            # Mismo error en ambos casos: un usuario ajeno no puede saber si existe.
            raise TenantNotFoundError()
        if require_active and not tenant.is_active:
            raise TenantNotActiveError()
        return TenantAccess(tenant=tenant, role=membership.role)
