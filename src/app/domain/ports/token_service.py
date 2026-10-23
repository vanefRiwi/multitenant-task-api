from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    expires_at: datetime


class TokenService(ABC):
    @abstractmethod
    def issue(self, user_id: UUID) -> AccessToken: ...

    @abstractmethod
    def verify(self, token: str) -> UUID:
        """Valida firma, expiración y emisor. Devuelve el id del usuario (claim `sub`).
        Lanza AuthenticationError si el token no es válido."""
