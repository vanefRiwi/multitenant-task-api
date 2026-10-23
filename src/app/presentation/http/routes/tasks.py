from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.application.tasks.create_task import CreateTask
from app.application.tasks.delete_task import DeleteTask
from app.application.tasks.get_task import GetTask
from app.application.tasks.list_tasks import ListTasks
from app.application.tasks.update_task import UpdateTask
from app.domain.entities.task import Task
from app.domain.enums import TaskPriority, TaskStatus
from app.domain.repositories.task_repository import TaskFilters
from app.presentation.http.dependencies import (
    CurrentUser,
    get_create_task,
    get_delete_task,
    get_get_task,
    get_list_tasks,
    get_update_task,
)
from app.presentation.http.schemas.tasks import (
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)

router = APIRouter(prefix="/tenants/{tenant_id}/tasks", tags=["Tasks"])


def to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
def create_task(
    tenant_id: UUID,
    body: TaskCreateRequest,
    user: CurrentUser,
    use_case: Annotated[CreateTask, Depends(get_create_task)],
) -> TaskResponse:
    task = use_case.execute(created_by=user.id, **body.model_dump())
    return to_response(task)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    tenant_id: UUID,
    use_case: Annotated[ListTasks, Depends(get_list_tasks)],
    limit: Annotated[int, Query(ge=1, description="Máximo configurable (por defecto 100)")] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
) -> TaskListResponse:
    page = use_case.execute(
        limit=limit, offset=offset, filters=TaskFilters(status=status_filter, priority=priority)
    )
    return TaskListResponse(
        items=[to_response(t) for t in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    tenant_id: UUID, task_id: UUID, use_case: Annotated[GetTask, Depends(get_get_task)]
) -> TaskResponse:
    return to_response(use_case.execute(task_id))


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    tenant_id: UUID,
    task_id: UUID,
    body: TaskUpdateRequest,
    use_case: Annotated[UpdateTask, Depends(get_update_task)],
) -> TaskResponse:
    changes = body.model_dump(exclude_unset=True)
    return to_response(use_case.execute(task_id, changes))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    tenant_id: UUID, task_id: UUID, use_case: Annotated[DeleteTask, Depends(get_delete_task)]
) -> Response:
    use_case.execute(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
