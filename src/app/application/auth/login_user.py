from app.domain.exceptions import InvalidCredentialsError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.token_service import AccessToken, TokenService
from app.domain.repositories.user_repository import UserRepository


class LoginUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        # Hash ficticio para gastar el mismo tiempo cuando el email no existe
        # (evita adivinar qué emails están registrados midiendo tiempos).
        self._dummy_hash = hasher.hash("dummy-password-for-timing")

    def execute(self, email: str, password: str) -> AccessToken:
        user = self._users.get_by_email(email.strip().lower())
        if user is None:
            self._hasher.verify(password, self._dummy_hash)
            raise InvalidCredentialsError()
        if not self._hasher.verify(password, user.password_hash) or not user.is_active:
            raise InvalidCredentialsError()
        return self._tokens.issue(user.id)
