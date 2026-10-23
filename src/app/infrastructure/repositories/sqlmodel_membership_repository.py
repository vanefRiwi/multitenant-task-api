from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.domain.entities.tenant import Membership
from app.domain.entities.user import User
from app.domain.enums import MembershipRole
from app.domain.exceptions import MembershipAlreadyExistsError, MembershipNotFoundError
from app.domain.repositories.membership_repository import MembershipRepository
from app.infrastructure.models.central import MembershipModel, UserModel
from app.infrastructure.repositories.sqlmodel_user_repository import to_domain as user_to_domain


def to_domain(model: MembershipModel) -> Membership:
    return Membership(
        id=model.id,
        user_id=model.user_id,
        tenant_id=model.tenant_id,
        role=MembershipRole(model.role),
        created_at=model.created_at,
    )


class SqlModelMembershipRepository(MembershipRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _get_model(self, user_id: UUID, tenant_id: UUID) -> MembershipModel | None:
        return self._session.exec(
            select(MembershipModel).where(
                MembershipModel.user_id == user_id, MembershipModel.tenant_id == tenant_id
            )
        ).first()

    def get(self, user_id: UUID, tenant_id: UUID) -> Membership | None:
        model = self._get_model(user_id, tenant_id)
        return to_domain(model) if model else None

    def add(self, membership: Membership) -> Membership:
        self._session.add(
            MembershipModel(
                id=membership.id,
                user_id=membership.user_id,
                tenant_id=membership.tenant_id,
                role=membership.role.value,
                created_at=membership.created_at,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise MembershipAlreadyExistsError() from exc
        return membership

    def update(self, membership: Membership) -> Membership:
        model = self._get_model(membership.user_id, membership.tenant_id)
        if model is None:
            raise MembershipNotFoundError()
        model.role = membership.role.value
        self._session.add(model)
        self._session.flush()
        return membership

    def delete(self, membership: Membership) -> None:
        model = self._get_model(membership.user_id, membership.tenant_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def list_for_tenant(self, tenant_id: UUID) -> list[tuple[Membership, User]]:
        rows = self._session.exec(
            select(MembershipModel, UserModel)
            .join(UserModel, col(UserModel.id) == col(MembershipModel.user_id))
            .where(MembershipModel.tenant_id == tenant_id)
            .order_by(col(MembershipModel.created_at))
        ).all()
        return [(to_domain(m), user_to_domain(u)) for m, u in rows]

    def count_owners(self, tenant_id: UUID) -> int:
        return self._session.exec(
            select(func.count())
            .select_from(MembershipModel)
            .where(
                MembershipModel.tenant_id == tenant_id,
                MembershipModel.role == MembershipRole.OWNER.value,
            )
        ).one()
