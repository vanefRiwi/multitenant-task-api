from dataclasses import dataclass

from sqlalchemy import URL

from app.config.settings import Settings
from app.infrastructure.secrets.secret_provider import SecretProvider


@dataclass(frozen=True, slots=True)
class DatabaseCredentials:
    username: str
    password: str

    def __repr__(self) -> str:  # nunca imprimir la contraseña en logs
        return f"DatabaseCredentials(username={self.username!r}, password='***')"


def build_url(settings: Settings, credentials: DatabaseCredentials, database: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=credentials.username,
        password=credentials.password,
        host=settings.db_host,
        port=settings.db_port,
        database=database,
    )


def _resolve(
    secrets: SecretProvider, username: str, password: str | None, secret_arn: str | None
) -> DatabaseCredentials:
    if secret_arn:
        # Formato estándar de RDS: {"username": "...", "password": "..."}
        data = secrets.get_json(secret_arn)
        return DatabaseCredentials(username=data["username"], password=data["password"])
    if password is None:
        raise RuntimeError(f"Faltan credenciales para el usuario de base de datos {username!r}")
    return DatabaseCredentials(username=username, password=password)


def central_credentials(settings: Settings, secrets: SecretProvider) -> DatabaseCredentials:
    return _resolve(
        secrets,
        settings.central_db_user,
        settings.central_db_password,
        settings.central_db_secret_arn,
    )


def provisioner_credentials(settings: Settings, secrets: SecretProvider) -> DatabaseCredentials:
    return _resolve(
        secrets,
        settings.provisioner_db_user,
        settings.provisioner_db_password,
        settings.provisioner_db_secret_arn,
    )


def admin_credentials(settings: Settings, secrets: SecretProvider) -> DatabaseCredentials:
    return _resolve(
        secrets, settings.admin_db_user, settings.admin_db_password, settings.admin_db_secret_arn
    )
