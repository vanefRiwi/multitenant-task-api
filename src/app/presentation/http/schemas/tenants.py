from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domain.enums import MembershipRole, TenantStatus
from app.presentation.http.schemas.common import RequestModel


class TenantCreateRequest(RequestModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TenantResponse(BaseModel):
    # Ni database_name ni secret_arn salen nunca en la API.
    id: UUID
    name: str
    slug: str
    status: TenantStatus
    role: MembershipRole
    created_at: datetime


class MemberAddRequest(RequestModel):
    email: EmailStr = Field(max_length=255)
    role: MembershipRole = MembershipRole.MEMBER


class MemberRoleUpdateRequest(RequestModel):
    role: MembershipRole


class MemberResponse(BaseModel):
    user_id: UUID
    email: str
    role: MembershipRole
    created_at: datetime
