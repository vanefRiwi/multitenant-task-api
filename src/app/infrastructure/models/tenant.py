"""Tablas SQLModel de la base de datos de CADA tenant (solo `tasks`).

No hay columna tenant_id: el aislamiento lo da la base de datos independiente.
Tampoco hay FK a users porque users vive en otra base de datos (control_db)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, Text
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel

tenant_registry = registry()


class TenantBase(SQLModel, registry=tenant_registry):
    pass


tenant_metadata = tenant_registry.metadata


class TaskModel(TenantBase, table=True):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')", name="ck_tasks_status"
        ),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_tasks_priority"),
    )

    id: UUID = Field(primary_key=True)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(max_length=20, index=True)
    priority: str = Field(max_length=20)
    due_date: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_by: UUID = Field(index=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
