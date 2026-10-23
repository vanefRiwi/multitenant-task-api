from uuid import UUID

from app.domain.entities.tenant import Membership, TenantAccess
from app.domain.enums import MembershipRole
from app.domain.exceptions import LastOwnerError, MembershipNotFoundError, PermissionDeniedError
from app.domain.repositories.membership_repository import MembershipRepository


class ChangeMemberRole:
    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    def execute(self, access: TenantAccess, user_id: UUID, role: MembershipRole) -> Membership:
        if not access.is_owner:
            raise PermissionDeniedError("Solo un owner puede cambiar roles")
        membership = self._memberships.get(user_id, access.tenant.id)
        if membership is None:
            raise MembershipNotFoundError()
        if (
            membership.is_owner
            and role != MembershipRole.OWNER
            and self._memberships.count_owners(access.tenant.id) <= 1
        ):
            raise LastOwnerError()
        membership.role = role
        return self._memberships.update(membership)
