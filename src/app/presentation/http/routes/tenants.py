from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.application.memberships.add_member import AddMember
from app.application.memberships.change_member_role import ChangeMemberRole
from app.application.memberships.list_members import ListMembers
from app.application.memberships.remove_member import RemoveMember
from app.application.tenants.create_tenant import CreateTenant
from app.application.tenants.list_tenants import ListTenants
from app.domain.entities.tenant import Membership, TenantAccess
from app.domain.entities.user import User
from app.presentation.http.dependencies import (
    ActiveTenantAccess,
    CurrentUser,
    get_add_member,
    get_change_member_role,
    get_create_tenant,
    get_list_members,
    get_list_tenants,
    get_remove_member,
    get_tenant_access_any_status,
)
from app.presentation.http.schemas.tenants import (
    MemberAddRequest,
    MemberResponse,
    MemberRoleUpdateRequest,
    TenantCreateRequest,
    TenantResponse,
)

router = APIRouter(prefix="/tenants", tags=["Tenants"])
members_router = APIRouter(prefix="/tenants/{tenant_id}/members", tags=["Memberships"])


def to_response(access: TenantAccess) -> TenantResponse:
    tenant = access.tenant
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        role=access.role,
        created_at=tenant.created_at,
    )


def member_to_response(membership: Membership, user: User) -> MemberResponse:
    return MemberResponse(
        user_id=user.id, email=user.email, role=membership.role, created_at=membership.created_at
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TenantResponse,
    responses={503: {"description": "La provisión falló; el tenant queda en estado 'failed'"}},
)
def create_tenant(
    body: TenantCreateRequest,
    user: CurrentUser,
    use_case: Annotated[CreateTenant, Depends(get_create_tenant)],
) -> TenantResponse:
    return to_response(use_case.execute(user, body.name, body.slug))


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    user: CurrentUser, use_case: Annotated[ListTenants, Depends(get_list_tenants)]
) -> list[TenantResponse]:
    return [to_response(access) for access in use_case.execute(user.id)]


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    access: Annotated[TenantAccess, Depends(get_tenant_access_any_status)],
) -> TenantResponse:
    return to_response(access)


@members_router.get("", response_model=list[MemberResponse])
def list_members(
    access: ActiveTenantAccess, use_case: Annotated[ListMembers, Depends(get_list_members)]
) -> list[MemberResponse]:
    return [member_to_response(m, u) for m, u in use_case.execute(access)]


@members_router.post("", status_code=status.HTTP_201_CREATED, response_model=MemberResponse)
def add_member(
    body: MemberAddRequest,
    access: ActiveTenantAccess,
    use_case: Annotated[AddMember, Depends(get_add_member)],
) -> MemberResponse:
    membership = use_case.execute(access, body.email, body.role)
    return MemberResponse(
        user_id=membership.user_id,
        email=body.email.lower(),
        role=membership.role,
        created_at=membership.created_at,
    )


@members_router.patch("/{user_id}", response_model=MemberResponse)
def change_member_role(
    user_id: UUID,
    body: MemberRoleUpdateRequest,
    access: ActiveTenantAccess,
    use_case: Annotated[ChangeMemberRole, Depends(get_change_member_role)],
    list_use_case: Annotated[ListMembers, Depends(get_list_members)],
) -> MemberResponse:
    use_case.execute(access, user_id, body.role)
    membership, user = next(
        (m, u) for m, u in list_use_case.execute(access) if m.user_id == user_id
    )
    return member_to_response(membership, user)


@members_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: UUID,
    user: CurrentUser,
    access: ActiveTenantAccess,
    use_case: Annotated[RemoveMember, Depends(get_remove_member)],
) -> Response:
    use_case.execute(access, user.id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
