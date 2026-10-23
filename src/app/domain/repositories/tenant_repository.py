from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.tenant import Tenant, TenantAccess


class TenantRepository(ABC):
    @abstractmethod
    def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...

    @abstractmethod
    def get_by_slug(self, slug: str) -> Tenant | None: ...

    @abstractmethod
    def add(self, tenant: Tenant) -> Tenant:
        """Inserta el tenant. Lanza TenantSlugAlreadyExistsError si el slug ya existe."""

    @abstractmethod
    def update(self, tenant: Tenant) -> Tenant: ...

    @abstractmethod
    def list_for_user(self, user_id: UUID) -> list[TenantAccess]:
        """Tenants de los que el usuario es miembro, con su rol."""

    @abstractmethod
    def list_all(self) -> list[Tenant]:
        """Solo para procesos operativos (migraciones de tenants)."""
