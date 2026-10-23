from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.tenant import Membership
from app.domain.entities.user import User


class MembershipRepository(ABC):
    @abstractmethod
    def get(self, user_id: UUID, tenant_id: UUID) -> Membership | None: ...

    @abstractmethod
    def add(self, membership: Membership) -> Membership:
        """Inserta la membresía. Lanza MembershipAlreadyExistsError si ya existe."""

    @abstractmethod
    def update(self, membership: Membership) -> Membership: ...

    @abstractmethod
    def delete(self, membership: Membership) -> None: ...

    @abstractmethod
    def list_for_tenant(self, tenant_id: UUID) -> list[tuple[Membership, User]]: ...

    @abstractmethod
    def count_owners(self, tenant_id: UUID) -> int: ...
