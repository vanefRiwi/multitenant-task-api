from uuid import UUID

from app.domain.entities.tenant import TenantAccess
from app.domain.exceptions import LastOwnerError, MembershipNotFoundError, PermissionDeniedError
from app.domain.repositories.membership_repository import MembershipRepository


class RemoveMember:
    """Revoca el acceso de un usuario a la organización. A partir de la siguiente
    petición, ResolveTenant ya no lo autoriza (aunque su JWT siga vigente)."""

    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    def execute(self, access: TenantAccess, current_user_id: UUID, user_id: UUID) -> None:
        leaving_by_themselves = current_user_id == user_id
        if not access.is_owner and not leaving_by_themselves:
            raise PermissionDeniedError("Solo un owner puede quitar miembros")
        membership = self._memberships.get(user_id, access.tenant.id)
        if membership is None:
            raise MembershipNotFoundError()
        if membership.is_owner and self._memberships.count_owners(access.tenant.id) <= 1:
            raise LastOwnerError()
        self._memberships.delete(membership)
