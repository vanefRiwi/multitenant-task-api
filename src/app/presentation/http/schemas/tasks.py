from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from app.domain.enums import TaskPriority, TaskStatus
from app.presentation.http.schemas.common import RequestModel


class TaskCreateRequest(RequestModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: AwareDatetime | None = None


class TaskUpdateRequest(RequestModel):
    """PATCH: todos los campos son opcionales; solo se cambian los enviados."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: AwareDatetime | None = None


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    limit: int
    offset: int
