from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.entities.user import User
from app.domain.exceptions import UserAlreadyExistsError
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.models.central import UserModel


def to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        is_active=model.is_active,
        created_at=model.created_at,
    )


class SqlModelUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        model = self._session.get(UserModel, user_id)
        return to_domain(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        model = self._session.exec(select(UserModel).where(UserModel.email == email)).first()
        return to_domain(model) if model else None

    def add(self, user: User) -> User:
        self._session.add(
            UserModel(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                is_active=user.is_active,
                created_at=user.created_at,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise UserAlreadyExistsError() from exc
        return user
