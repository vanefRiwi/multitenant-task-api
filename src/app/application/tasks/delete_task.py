from uuid import UUID

from app.domain.exceptions import TaskNotFoundError
from app.domain.repositories.task_repository import TaskRepository


class DeleteTask:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    def execute(self, task_id: UUID) -> None:
        task = self._tasks.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError()
        self._tasks.delete(task)
