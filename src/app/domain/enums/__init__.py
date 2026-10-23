"""Enumeraciones del dominio. Son StrEnum para que se serialicen como texto."""

from enum import StrEnum


class TenantStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    SUSPENDED = "suspended"


class MembershipRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
