from typing import Any
from uuid import UUID

from app.domain.entities.task import Task
from app.domain.exceptions import TaskNotFoundError, ValidationError
from app.domain.repositories.task_repository import TaskRepository


class UpdateTask:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    def execute(self, task_id: UUID, changes: dict[str, Any]) -> Task:
        """`changes` contiene solo los campos que envió el cliente (PATCH parcial)."""
        if not changes:
            raise ValidationError("Envía al menos un campo para actualizar")
        task = self._tasks.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError()
        task.apply_changes(**changes, fields_set=set(changes))
        return self._tasks.update(task)
