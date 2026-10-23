"""Tablas SQLModel de control_db (usuarios, tenants y membresías).

Viven en infraestructura, no en el dominio: el dominio trabaja con dataclasses puras
y los repositorios traducen entre ambos mundos."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel

central_registry = registry()


class CentralBase(SQLModel, registry=central_registry):
    pass


central_metadata = central_registry.metadata


class UserModel(CentralBase, table=True):
    __tablename__ = "users"

    id: UUID = Field(primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class TenantModel(CentralBase, table=True):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('provisioning', 'active', 'failed', 'suspended')",
            name="ck_tenants_status",
        ),
    )

    id: UUID = Field(primary_key=True)
    name: str = Field(max_length=150)
    slug: str = Field(max_length=100, unique=True)
    database_name: str = Field(max_length=63, unique=True)
    secret_arn: str | None = Field(default=None, max_length=512)
    status: str = Field(max_length=20)
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class MembershipModel(CentralBase, table=True):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),
        CheckConstraint("role IN ('owner', 'member')", name="ck_memberships_role"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    tenant_id: UUID = Field(
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    role: str = Field(max_length=20)
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
