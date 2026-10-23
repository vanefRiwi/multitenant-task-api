from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.utils import utc_now


@dataclass(slots=True)
class User:
    email: str
    password_hash: str
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        # El email se normaliza siempre igual para que la unicidad funcione.
        self.email = self.email.strip().lower()
