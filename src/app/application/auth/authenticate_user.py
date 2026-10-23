from app.domain.entities.user import User
from app.domain.exceptions import AuthenticationError
from app.domain.ports.token_service import TokenService
from app.domain.repositories.user_repository import UserRepository


class AuthenticateUser:
    """Convierte un JWT en el usuario autenticado (lo usa GET /auth/me y todas las rutas)."""

    def __init__(self, users: UserRepository, tokens: TokenService) -> None:
        self._users = users
        self._tokens = tokens

    def execute(self, token: str) -> User:
        user_id = self._tokens.verify(token)
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError()
        return user
