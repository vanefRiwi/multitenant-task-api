from uuid import UUID

from sqlmodel import Session, col, func, select

from app.domain.entities.task import Task
from app.domain.enums import TaskPriority, TaskStatus
from app.domain.exceptions import TaskNotFoundError
from app.domain.repositories.task_repository import TaskFilters, TaskRepository
from app.infrastructure.models.tenant import TaskModel


def to_domain(model: TaskModel) -> Task:
    return Task(
        id=model.id,
        title=model.title,
        description=model.description,
        status=TaskStatus(model.status),
        priority=TaskPriority(model.priority),
        due_date=model.due_date,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _copy_into(task: Task, model: TaskModel) -> None:
    model.title = task.title
    model.description = task.description
    model.status = task.status.value
    model.priority = task.priority.value
    model.due_date = task.due_date
    model.updated_at = task.updated_at


class SqlModelTaskRepository(TaskRepository):
    """La sesión recibida ya apunta a la base de datos del tenant autorizado."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, task_id: UUID) -> Task | None:
        model = self._session.get(TaskModel, task_id)
        return to_domain(model) if model else None

    def list(self, *, limit: int, offset: int, filters: TaskFilters) -> tuple[list[Task], int]:
        conditions = []
        if filters.status is not None:
            conditions.append(col(TaskModel.status) == filters.status.value)
        if filters.priority is not None:
            conditions.append(col(TaskModel.priority) == filters.priority.value)

        total = self._session.exec(
            select(func.count()).select_from(TaskModel).where(*conditions)
        ).one()
        models = self._session.exec(
            select(TaskModel)
            .where(*conditions)
            .order_by(col(TaskModel.created_at).desc(), col(TaskModel.id))
            .limit(limit)
            .offset(offset)
        ).all()
        return [to_domain(m) for m in models], total

    def add(self, task: Task) -> Task:
        model = TaskModel(
            id=task.id,
            title=task.title,
            description=task.description,
            status=task.status.value,
            priority=task.priority.value,
            due_date=task.due_date,
            created_by=task.created_by,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.add(model)
        self._session.flush()
        return task

    def update(self, task: Task) -> Task:
        model = self._session.get(TaskModel, task.id)
        if model is None:
            raise TaskNotFoundError()
        _copy_into(task, model)
        self._session.add(model)
        self._session.flush()
        return task

    def delete(self, task: Task) -> None:
        model = self._session.get(TaskModel, task.id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
