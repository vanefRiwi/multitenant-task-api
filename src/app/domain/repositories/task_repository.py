from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.task import Task
from app.domain.enums import TaskPriority, TaskStatus


@dataclass(frozen=True, slots=True)
class TaskFilters:
    status: TaskStatus | None = None
    priority: TaskPriority | None = None


class TaskRepository(ABC):
    """Repositorio de tareas de UN tenant.

    No recibe tenant_id: la instancia ya está ligada a la sesión de la base de
    datos del tenant, así que es imposible consultar tareas de otro tenant con ella.
    """

    @abstractmethod
    def get_by_id(self, task_id: UUID) -> Task | None: ...

    @abstractmethod
    def list(self, *, limit: int, offset: int, filters: TaskFilters) -> tuple[list[Task], int]:
        """Devuelve (página de tareas, total que cumple los filtros)."""

    @abstractmethod
    def add(self, task: Task) -> Task: ...

    @abstractmethod
    def update(self, task: Task) -> Task: ...

    @abstractmethod
    def delete(self, task: Task) -> None: ...
