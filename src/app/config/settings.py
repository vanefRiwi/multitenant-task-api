"""Configuración leída de variables de entorno (o de un archivo .env en local).

Las credenciales se pueden dar de dos formas:
- Local / CI: usuario y contraseña directamente (`CENTRAL_DB_USER`, `CENTRAL_DB_PASSWORD`...).
- AWS: el ARN de un secreto de Secrets Manager (`CENTRAL_DB_SECRET_ARN`...). La Lambda lee
  el secreto al arrancar; la contraseña nunca está en variables de entorno ni en el código.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    expose_docs: bool = True

    # --- PostgreSQL (host común: control_db y bases de tenants viven en la misma instancia)
    db_host: str = "localhost"
    db_port: int = 5432
    db_connect_timeout_seconds: int = 5
    control_db_name: str = "control_db"
    maintenance_db_name: str = "postgres"

    # Usuario de la API para control_db (solo SELECT/INSERT/UPDATE/DELETE).
    central_db_user: str = "app_central"
    central_db_password: str | None = None
    central_db_secret_arn: str | None = None
    central_pool_size: int = 2
    central_max_overflow: int = 2

    # Usuario de provisión (CREATEDB + CREATEROLE). Credencial separada, solo para crear
    # bases de tenants y aplicar sus migraciones.
    provisioner_db_user: str = "tenant_provisioner"
    provisioner_db_password: str | None = None
    provisioner_db_secret_arn: str | None = None

    # Usuario administrador (maestro de RDS). Solo lo usa el bootstrap/migración central.
    admin_db_user: str = "postgres"
    admin_db_password: str | None = None
    admin_db_secret_arn: str | None = None

    # --- Tenants
    tenant_db_prefix: str = "tenant_"
    tenant_db_connection_limit: int = 5
    tenant_engine_cache_size: int = 20
    tenant_engine_ttl_seconds: int = 300
    tenant_pool_size: int = 1
    tenant_max_overflow: int = 1

    # --- Secretos
    secret_provider: Literal["local", "aws"] = "local"
    local_secrets_dir: str = ".local-secrets"
    tenant_secret_prefix: str = "multitenant-task-api/local"
    aws_region: str | None = None

    # --- JWT
    jwt_secret: str | None = None
    jwt_secret_arn: str | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "multitenant-task-api"
    jwt_expires_minutes: int = Field(default=60, ge=1, le=24 * 60)

    # --- Paginación
    pagination_default_limit: int = 20
    pagination_max_limit: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
