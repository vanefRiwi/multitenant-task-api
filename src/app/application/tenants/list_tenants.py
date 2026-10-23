from uuid import UUID

from app.domain.entities.tenant import TenantAccess
from app.domain.repositories.tenant_repository import TenantRepository


class ListTenants:
    def __init__(self, tenants: TenantRepository) -> None:
        self._tenants = tenants

    def execute(self, user_id: UUID) -> list[TenantAccess]:
        return self._tenants.list_for_user(user_id)
