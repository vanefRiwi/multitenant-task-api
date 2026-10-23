from app.domain.entities.tenant import Membership, TenantAccess
from app.domain.enums import MembershipRole
from app.domain.exceptions import (
    MembershipAlreadyExistsError,
    PermissionDeniedError,
    UserNotFoundError,
)
from app.domain.repositories.membership_repository import MembershipRepository
from app.domain.repositories.user_repository import UserRepository


class AddMember:
    def __init__(self, users: UserRepository, memberships: MembershipRepository) -> None:
        self._users = users
        self._memberships = memberships

    def execute(self, access: TenantAccess, email: str, role: MembershipRole) -> Membership:
        if not access.is_owner:
            raise PermissionDeniedError("Solo un owner puede añadir miembros")
        user = self._users.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            raise UserNotFoundError("No existe un usuario activo con ese email")
        if self._memberships.get(user.id, access.tenant.id) is not None:
            raise MembershipAlreadyExistsError()
        return self._memberships.add(
            Membership(user_id=user.id, tenant_id=access.tenant.id, role=role)
        )
