from app.domain.entities.tenant import Membership, TenantAccess
from app.domain.entities.user import User
from app.domain.repositories.membership_repository import MembershipRepository


class ListMembers:
    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    def execute(self, access: TenantAccess) -> list[tuple[Membership, User]]:
        return self._memberships.list_for_tenant(access.tenant.id)
