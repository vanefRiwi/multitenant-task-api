from app.domain.entities.user import User
from app.domain.exceptions import UserAlreadyExistsError, ValidationError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.repositories.user_repository import UserRepository

MIN_PASSWORD_LENGTH = 8


class RegisterUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    def execute(self, email: str, password: str) -> User:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
            )
        user = User(email=email, password_hash=self._hasher.hash(password))
        if self._users.get_by_email(user.email) is not None:
            raise UserAlreadyExistsError()
        # El registro público nunca concede privilegios globales: no hay campo de rol global.
        return self._users.add(user)
