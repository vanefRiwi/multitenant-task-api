import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums import MembershipRole, TenantStatus
from app.domain.exceptions import ValidationError
from app.domain.utils import utc_now

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Nombre de base de datos/rol válido en PostgreSQL y seguro para usarlo como identificador.
DATABASE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def build_database_name(prefix: str, tenant_id: UUID) -> str:
    """El nombre de la BD lo genera el sistema, nunca el cliente."""
    name = f"{prefix}{tenant_id.hex}"
    if not DATABASE_NAME_PATTERN.fullmatch(name):
        raise ValidationError("Prefijo de base de datos de tenant inválido")
    return name


@dataclass(slots=True)
class Tenant:
    name: str
    slug: str
    database_name: str
    status: TenantStatus = TenantStatus.PROVISIONING
    secret_arn: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError("El nombre de la organización es obligatorio")
        if not SLUG_PATTERN.fullmatch(self.slug):
            raise ValidationError(
                "El slug solo admite minúsculas, números y guiones (p. ej. 'acme-corp')"
            )
        if not DATABASE_NAME_PATTERN.fullmatch(self.database_name):
            raise ValidationError("Nombre de base de datos inválido")

    @property
    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE

    def mark_active(self, secret_arn: str) -> None:
        self.secret_arn = secret_arn
        self.status = TenantStatus.ACTIVE

    def mark_failed(self) -> None:
        self.status = TenantStatus.FAILED


@dataclass(slots=True)
class Membership:
    user_id: UUID
    tenant_id: UUID
    role: MembershipRole = MembershipRole.MEMBER
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    @property
    def is_owner(self) -> bool:
        return self.role == MembershipRole.OWNER


@dataclass(frozen=True, slots=True)
class TenantAccess:
    """Resultado de autorizar a un usuario sobre un tenant: el tenant + su rol."""

    tenant: Tenant
    role: MembershipRole

    @property
    def is_owner(self) -> bool:
        return self.role == MembershipRole.OWNER
