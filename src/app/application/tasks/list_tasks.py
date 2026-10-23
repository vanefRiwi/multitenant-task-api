from dataclasses import dataclass

from app.domain.entities.task import Task
from app.domain.exceptions import ValidationError
from app.domain.repositories.task_repository import TaskFilters, TaskRepository


@dataclass(frozen=True, slots=True)
class TaskPage:
    items: list[Task]
    total: int
    limit: int
    offset: int


class ListTasks:
    def __init__(self, tasks: TaskRepository, max_limit: int) -> None:
        self._tasks = tasks
        self._max_limit = max_limit

    def execute(self, *, limit: int, offset: int, filters: TaskFilters) -> TaskPage:
        if limit < 1 or limit > self._max_limit:
            raise ValidationError(f"limit debe estar entre 1 y {self._max_limit}")
        if offset < 0:
            raise ValidationError("offset no puede ser negativo")
        items, total = self._tasks.list(limit=limit, offset=offset, filters=filters)
        return TaskPage(items=items, total=total, limit=limit, offset=offset)
