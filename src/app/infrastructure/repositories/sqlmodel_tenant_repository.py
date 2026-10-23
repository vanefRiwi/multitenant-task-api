from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.entities.tenant import Tenant, TenantAccess
from app.domain.enums import MembershipRole, TenantStatus
from app.domain.exceptions import TenantNotFoundError, TenantSlugAlreadyExistsError
from app.domain.repositories.tenant_repository import TenantRepository
from app.infrastructure.models.central import MembershipModel, TenantModel


def to_domain(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        name=model.name,
        slug=model.slug,
        database_name=model.database_name,
        secret_arn=model.secret_arn,
        status=TenantStatus(model.status),
        created_at=model.created_at,
    )


class SqlModelTenantRepository(TenantRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        model = self._session.get(TenantModel, tenant_id)
        return to_domain(model) if model else None

    def get_by_slug(self, slug: str) -> Tenant | None:
        model = self._session.exec(select(TenantModel).where(TenantModel.slug == slug)).first()
        return to_domain(model) if model else None

    def add(self, tenant: Tenant) -> Tenant:
        self._session.add(
            TenantModel(
                id=tenant.id,
                name=tenant.name,
                slug=tenant.slug,
                database_name=tenant.database_name,
                secret_arn=tenant.secret_arn,
                status=tenant.status.value,
                created_at=tenant.created_at,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise TenantSlugAlreadyExistsError() from exc
        return tenant

    def update(self, tenant: Tenant) -> Tenant:
        model = self._session.get(TenantModel, tenant.id)
        if model is None:
            raise TenantNotFoundError()
        model.name = tenant.name
        model.status = tenant.status.value
        model.secret_arn = tenant.secret_arn
        self._session.add(model)
        self._session.flush()
        return tenant

    def list_for_user(self, user_id: UUID) -> list[TenantAccess]:
        rows = self._session.exec(
            select(TenantModel, MembershipModel.role)
            .join(MembershipModel, col(MembershipModel.tenant_id) == col(TenantModel.id))
            .where(MembershipModel.user_id == user_id)
            .order_by(col(TenantModel.created_at))
        ).all()
        return [TenantAccess(tenant=to_domain(t), role=MembershipRole(role)) for t, role in rows]

    def list_all(self) -> list[Tenant]:
        models = self._session.exec(select(TenantModel).order_by(col(TenantModel.created_at)))
        return [to_domain(m) for m in models.all()]
