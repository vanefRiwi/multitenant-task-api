from datetime import datetime
from uuid import UUID

from app.domain.entities.task import Task
from app.domain.enums import TaskPriority, TaskStatus
from app.domain.repositories.task_repository import TaskRepository


class CreateTask:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    def execute(
        self,
        *,
        created_by: UUID,
        title: str,
        description: str | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: datetime | None = None,
    ) -> Task:
        # created_by sale del JWT, nunca del cuerpo de la petición.
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            created_by=created_by,
        )
        return self._tasks.add(task)
