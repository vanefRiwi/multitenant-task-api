from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.domain.entities.task import Task
from app.domain.entities.tenant import Membership, Tenant
from app.domain.entities.user import User
from app.domain.enums import MembershipRole, TaskPriority, TaskStatus
from app.domain.exceptions import MembershipAlreadyExistsError, UserAlreadyExistsError
from app.domain.repositories.task_repository import TaskFilters
from app.infrastructure.container import Container
from app.infrastructure.repositories.sqlmodel_membership_repository import (
    SqlModelMembershipRepository,
)
from app.infrastructure.repositories.sqlmodel_task_repository import SqlModelTaskRepository
from app.infrastructure.repositories.sqlmodel_tenant_repository import SqlModelTenantRepository
from app.infrastructure.repositories.sqlmodel_user_repository import SqlModelUserRepository
from tests.helpers import create_tenant, new_user


@pytest.fixture
def session(container: Container) -> Iterator[Session]:
    with Session(container.central_engine) as session:
        yield session
        session.rollback()


def test_user_repository_roundtrip_and_unique_email(session: Session) -> None:
    repo = SqlModelUserRepository(session)
    user = repo.add(User(email="Repo@Example.com", password_hash="hash"))
    assert repo.get_by_id(user.id) == user
    assert repo.get_by_email("repo@example.com") == user
    with pytest.raises(UserAlreadyExistsError):
        repo.add(User(email="repo@example.com", password_hash="otro"))


def test_tenant_and_membership_repositories(session: Session) -> None:
    users = SqlModelUserRepository(session)
    tenants = SqlModelTenantRepository(session)
    memberships = SqlModelMembershipRepository(session)
    owner = users.add(User(email="o@example.com", password_hash="h"))
    member = users.add(User(email="m@example.com", password_hash="h"))
    tenant = tenants.add(Tenant(name="Acme", slug="acme", database_name="test_tenant_x"))
    memberships.add(Membership(user_id=owner.id, tenant_id=tenant.id, role=MembershipRole.OWNER))
    memberships.add(Membership(user_id=member.id, tenant_id=tenant.id))

    assert memberships.count_owners(tenant.id) == 1
    assert [a.role for a in tenants.list_for_user(member.id)] == [MembershipRole.MEMBER]
    assert tenants.get_by_slug("acme") == tenant
    assert {u.email for _, u in memberships.list_for_tenant(tenant.id)} == {
        "o@example.com",
        "m@example.com",
    }
    with pytest.raises(MembershipAlreadyExistsError):
        memberships.add(Membership(user_id=owner.id, tenant_id=tenant.id))


def test_task_repository_on_a_tenant_database(client: TestClient, container: Container) -> None:
    _, headers = new_user(client)
    tenant_id = create_tenant(client, headers)["id"]
    with Session(container.central_engine) as central:
        tenant = SqlModelTenantRepository(central).get_by_id(UUID(tenant_id))
    assert tenant is not None

    sessions = container.tenant_databases.session(tenant)
    tenant_session = next(sessions)
    repo = SqlModelTaskRepository(tenant_session)
    created_by = uuid4()
    for i, (status, priority) in enumerate(
        [(TaskStatus.PENDING, TaskPriority.LOW), (TaskStatus.COMPLETED, TaskPriority.HIGH)] * 3
    ):
        repo.add(Task(title=f"t{i}", created_by=created_by, status=status, priority=priority))

    items, total = repo.list(limit=4, offset=0, filters=TaskFilters())
    assert total == 6 and len(items) == 4
    items, total = repo.list(limit=10, offset=0, filters=TaskFilters(status=TaskStatus.COMPLETED))
    assert total == 3 and all(t.status == TaskStatus.COMPLETED for t in items)

    task = items[0]
    task.apply_changes(title="nuevo", fields_set={"title"})
    repo.update(task)
    assert repo.get_by_id(task.id).title == "nuevo"  # type: ignore[union-attr]
    repo.delete(task)
    assert repo.get_by_id(task.id) is None
    with pytest.raises(StopIteration):
        next(sessions)  # cierra la sesión (commit)
