from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums import TaskPriority, TaskStatus
from app.domain.exceptions import ValidationError
from app.domain.utils import utc_now

TITLE_MAX_LENGTH = 200


@dataclass(slots=True)
class Task:
    title: str
    created_by: UUID
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.title = self._clean_title(self.title)

    @staticmethod
    def _clean_title(title: str) -> str:
        title = title.strip()
        if not title:
            raise ValidationError("El título de la tarea es obligatorio")
        if len(title) > TITLE_MAX_LENGTH:
            raise ValidationError(f"El título admite como máximo {TITLE_MAX_LENGTH} caracteres")
        return title

    def apply_changes(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        due_date: datetime | None = None,
        fields_set: set[str],
    ) -> None:
        """Aplica un PATCH. `fields_set` dice qué campos envió el cliente,
        para distinguir "no enviado" de "enviado como null" (borrar)."""
        if "title" in fields_set:
            if title is None:
                raise ValidationError("El título no puede ser nulo")
            self.title = self._clean_title(title)
        if "description" in fields_set:
            self.description = description
        if "status" in fields_set:
            if status is None:
                raise ValidationError("El estado no puede ser nulo")
            self.status = status
        if "priority" in fields_set:
            if priority is None:
                raise ValidationError("La prioridad no puede ser nula")
            self.priority = priority
        if "due_date" in fields_set:
            self.due_date = due_date
        self.updated_at = utc_now()
