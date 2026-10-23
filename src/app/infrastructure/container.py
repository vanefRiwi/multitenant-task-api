"""Construcción de los recursos de infraestructura de un proceso (una vez por arranque).

En Lambda esto ocurre en el "cold start" y se reutiliza entre invocaciones del mismo
contenedor. Solo contiene recursos compartidos y sin estado de petición."""

from dataclasses import dataclass

from sqlalchemy import Engine

from app.config.settings import Settings
from app.infrastructure.database.central import create_central_engine
from app.infrastructure.database.credentials import central_credentials, provisioner_credentials
from app.infrastructure.secrets.secret_provider import (
    AwsSecretsManagerProvider,
    LocalFileSecretProvider,
    SecretProvider,
)
from app.infrastructure.security.jwt import JwtTokenService
from app.infrastructure.security.password import Argon2PasswordHasher
from app.infrastructure.tenancy.postgres_tenant_provisioner import PostgresTenantProvisioner
from app.infrastructure.tenancy.tenant_database_factory import TenantDatabaseFactory


@dataclass
class Container:
    settings: Settings
    secrets: SecretProvider
    central_engine: Engine
    tenant_databases: TenantDatabaseFactory
    provisioner: PostgresTenantProvisioner
    password_hasher: Argon2PasswordHasher
    token_service: JwtTokenService

    def close(self) -> None:
        self.tenant_databases.dispose_all()
        self.central_engine.dispose()


def build_secret_provider(settings: Settings) -> SecretProvider:
    if settings.secret_provider == "aws":
        return AwsSecretsManagerProvider(region=settings.aws_region)
    return LocalFileSecretProvider(settings.local_secrets_dir)


def resolve_jwt_secret(settings: Settings, secrets: SecretProvider) -> str:
    if settings.jwt_secret_arn:
        return secrets.get_string(settings.jwt_secret_arn).strip()
    if not settings.jwt_secret:
        raise RuntimeError("Configura JWT_SECRET o JWT_SECRET_ARN")
    return settings.jwt_secret


def build_container(settings: Settings, secrets: SecretProvider | None = None) -> Container:
    secrets = secrets or build_secret_provider(settings)
    return Container(
        settings=settings,
        secrets=secrets,
        central_engine=create_central_engine(settings, central_credentials(settings, secrets)),
        tenant_databases=TenantDatabaseFactory(settings, secrets),
        provisioner=PostgresTenantProvisioner(
            settings, provisioner_credentials(settings, secrets), secrets
        ),
        password_hasher=Argon2PasswordHasher(),
        token_service=JwtTokenService(
            secret=resolve_jwt_secret(settings, secrets),
            algorithm=settings.jwt_algorithm,
            issuer=settings.jwt_issuer,
            expires_minutes=settings.jwt_expires_minutes,
        ),
    )
