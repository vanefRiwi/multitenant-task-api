from datetime import timedelta
from uuid import UUID

import jwt

from app.domain.exceptions import AuthenticationError
from app.domain.ports.token_service import AccessToken, TokenService
from app.domain.utils import utc_now

MIN_SECRET_LENGTH = 32


class JwtTokenService(TokenService):
    def __init__(self, secret: str, algorithm: str, issuer: str, expires_minutes: int) -> None:
        if len(secret) < MIN_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET debe tener al menos {MIN_SECRET_LENGTH} caracteres")
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._expires = timedelta(minutes=expires_minutes)

    def issue(self, user_id: UUID) -> AccessToken:
        now = utc_now()
        expires_at = now + self._expires
        payload = {"sub": str(user_id), "iat": now, "exp": expires_at, "iss": self._issuer}
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return AccessToken(token=token, expires_at=expires_at)

    def verify(self, token: str) -> UUID:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                # Lista cerrada: rechaza "none" y cualquier algoritmo distinto al configurado.
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={"require": ["sub", "exp", "iat", "iss"]},
            )
            return UUID(str(payload["sub"]))
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("El token ha expirado") from exc
        except (jwt.InvalidTokenError, ValueError) as exc:
            raise AuthenticationError("Token inválido") from exc
