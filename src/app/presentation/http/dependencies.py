"""Punto de composición (inyección de dependencias).

Es el ÚNICO lugar de la capa de presentación que conoce las clases concretas de
infraestructura. Cada petición obtiene sus propias sesiones; nada de la petición se
guarda en variables globales.
"""

import threading
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.application.auth.authenticate_user import AuthenticateUser
from app.application.auth.login_user import LoginUser
from app.application.auth.register_user import RegisterUser
from app.application.memberships.add_member import AddMember
from app.application.memberships.change_member_role import ChangeMemberRole
from app.application.memberships.list_members import ListMembers
from app.application.memberships.remove_member import RemoveMember
from app.application.tasks.create_task import CreateTask
from app.application.tasks.delete_task import DeleteTask
from app.application.tasks.get_task import GetTask
from app.application.tasks.list_tasks import ListTasks
from app.application.tasks.update_task import UpdateTask
from app.application.tenants.create_tenant import CreateTenant
from app.application.tenants.list_tenants import ListTenants
from app.application.tenants.provision_tenant import ProvisionTenant
from app.application.tenants.resolve_tenant import ResolveTenant
from app.domain.entities.tenant import TenantAccess
from app.domain.entities.user import User
from app.domain.exceptions import AuthenticationError
from app.domain.repositories.membership_repository import MembershipRepository
from app.domain.repositories.task_repository import TaskRepository
from app.domain.repositories.tenant_repository import TenantRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.container import Container, build_container
from app.infrastructure.database.central import central_session
from app.infrastructure.database.unit_of_work import SqlModelUnitOfWork
from app.infrastructure.repositories.sqlmodel_membership_repository import (
    SqlModelMembershipRepository,
)
from app.infrastructure.repositories.sqlmodel_task_repository import SqlModelTaskRepository
from app.infrastructure.repositories.sqlmodel_tenant_repository import SqlModelTenantRepository
from app.infrastructure.repositories.sqlmodel_user_repository import SqlModelUserRepository

_container_lock = threading.Lock()
bearer_scheme = HTTPBearer(auto_error=False, description="JWT obtenido en /auth/login")


# --- Recursos del proceso -------------------------------------------------------------
def get_container(request: Request) -> Container:
    """El contenedor se crea en la primera petición (cold start) y se reutiliza."""
    state = request.app.state
    if state.container is None:
        with _container_lock:
            if state.container is None:
                state.container = build_container(state.settings)
    container: Container = state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


# --- Sesión central (control_db) ------------------------------------------------------
def get_central_session(container: ContainerDep) -> Iterator[Session]:
    yield from central_session(container.central_engine)


CentralSession = Annotated[Session, Depends(get_central_session, scope="function")]


def get_user_repository(session: CentralSession) -> UserRepository:
    return SqlModelUserRepository(session)


def get_tenant_repository(session: CentralSession) -> TenantRepository:
    return SqlModelTenantRepository(session)


def get_membership_repository(session: CentralSession) -> MembershipRepository:
    return SqlModelMembershipRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TenantRepo = Annotated[TenantRepository, Depends(get_tenant_repository)]
MembershipRepo = Annotated[MembershipRepository, Depends(get_membership_repository)]


# --- Autenticación --------------------------------------------------------------------
def get_register_user(users: UserRepo, container: ContainerDep) -> RegisterUser:
    return RegisterUser(users, container.password_hasher)


def get_login_user(users: UserRepo, container: ContainerDep) -> LoginUser:
    return LoginUser(users, container.password_hasher, container.token_service)


def get_current_user(
    users: UserRepo,
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    return AuthenticateUser(users, container.token_service).execute(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


# --- Tenants --------------------------------------------------------------------------
def get_create_tenant(
    tenants: TenantRepo,
    memberships: MembershipRepo,
    session: CentralSession,
    container: ContainerDep,
) -> CreateTenant:
    uow = SqlModelUnitOfWork(session)
    return CreateTenant(
        tenants,
        memberships,
        ProvisionTenant(tenants, container.provisioner, uow),
        uow,
        container.settings.tenant_db_prefix,
    )


def get_list_tenants(tenants: TenantRepo) -> ListTenants:
    return ListTenants(tenants)


def get_tenant_access_any_status(
    tenant_id: UUID, user: CurrentUser, tenants: TenantRepo, memberships: MembershipRepo
) -> TenantAccess:
    return ResolveTenant(tenants, memberships).execute(user.id, tenant_id, require_active=False)


def get_tenant_access(
    tenant_id: UUID, user: CurrentUser, tenants: TenantRepo, memberships: MembershipRepo
) -> TenantAccess:
    """Pasos 2-3 del aislamiento: JWT válido + tenant activo + membresía vigente."""
    return ResolveTenant(tenants, memberships).execute(user.id, tenant_id, require_active=True)


ActiveTenantAccess = Annotated[TenantAccess, Depends(get_tenant_access)]


# --- Membresías -----------------------------------------------------------------------
def get_add_member(users: UserRepo, memberships: MembershipRepo) -> AddMember:
    return AddMember(users, memberships)


def get_list_members(memberships: MembershipRepo) -> ListMembers:
    return ListMembers(memberships)


def get_change_member_role(memberships: MembershipRepo) -> ChangeMemberRole:
    return ChangeMemberRole(memberships)


def get_remove_member(memberships: MembershipRepo) -> RemoveMember:
    return RemoveMember(memberships)


# --- Base de datos del tenant ---------------------------------------------------------
def get_tenant_session(access: ActiveTenantAccess, container: ContainerDep) -> Iterator[Session]:
    """Paso 4: sesión de la BD del tenant ya autorizado. Se cierra siempre."""
    yield from container.tenant_databases.session(access.tenant)


TenantSession = Annotated[Session, Depends(get_tenant_session, scope="function")]


def get_task_repository(session: TenantSession) -> TaskRepository:
    return SqlModelTaskRepository(session)


TaskRepo = Annotated[TaskRepository, Depends(get_task_repository)]


def get_create_task(tasks: TaskRepo) -> CreateTask:
    return CreateTask(tasks)


def get_list_tasks(tasks: TaskRepo, container: ContainerDep) -> ListTasks:
    return ListTasks(tasks, container.settings.pagination_max_limit)


def get_get_task(tasks: TaskRepo) -> GetTask:
    return GetTask(tasks)


def get_update_task(tasks: TaskRepo) -> UpdateTask:
    return UpdateTask(tasks)


def get_delete_task(tasks: TaskRepo) -> DeleteTask:
    return DeleteTask(tasks)
