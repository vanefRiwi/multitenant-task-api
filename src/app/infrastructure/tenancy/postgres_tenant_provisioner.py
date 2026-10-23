"""Componente de provisión restringido: crea la base de datos de un tenant.

Usa una credencial SEPARADA (`tenant_provisioner`, con CREATEDB y CREATEROLE pero sin
superusuario). La credencial normal de la API no puede crear bases de datos.
"""

import logging
import secrets as pysecrets
from typing import Any

from sqlalchemy import Connection

from app.config.settings import Settings
from app.domain.entities.tenant import Tenant
from app.domain.ports.tenant_provisioner import TenantProvisioner
from app.infrastructure.database import pg_admin
from app.infrastructure.database.credentials import DatabaseCredentials, build_url
from app.infrastructure.database.engine import create_pg_engine
from app.infrastructure.database.migrations import VERSION_TABLES, upgrade_to_head
from app.infrastructure.secrets.secret_provider import SecretProvider

logger = logging.getLogger(__name__)

TENANT_ROLE_ATTRIBUTES = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"


def tenant_secret_name(settings: Settings, database_name: str) -> str:
    return f"{settings.tenant_secret_prefix}/tenants/{database_name}"


class PostgresTenantProvisioner(TenantProvisioner):
    def __init__(
        self,
        settings: Settings,
        credentials: DatabaseCredentials,
        secrets: SecretProvider,
    ) -> None:
        self._settings = settings
        self._credentials = credentials
        self._secrets = secrets

    def provision(self, tenant: Tenant) -> str:
        database = pg_admin.check_identifier(tenant.database_name)
        role = database  # un rol de PostgreSQL por tenant, con el mismo nombre que su BD
        password = pysecrets.token_urlsafe(32)

        # 3. Crear rol + base de datos y cerrar la BD al resto de usuarios.
        with (
            pg_admin.connect(
                self._settings, self._credentials, self._settings.maintenance_db_name
            ) as conn,
            conn.cursor() as cur,
        ):
            pg_admin.ensure_role(
                cur,
                role,
                password,
                TENANT_ROLE_ATTRIBUTES,
                connection_limit=self._settings.tenant_db_connection_limit,
            )
            pg_admin.ensure_database(cur, database)
            pg_admin.restrict_database(cur, database, role)

        # 4. Guardar credenciales en el gestor de secretos; en control_db solo va el ARN.
        secret_arn = self._secrets.put_json(
            tenant_secret_name(self._settings, database),
            {
                "engine": "postgres",
                "username": role,
                "password": password,
                "dbname": database,
                "host": self._settings.db_host,
                "port": self._settings.db_port,
            },
            description=f"Credenciales de la base de datos del tenant {tenant.id}",
        )

        # 5. Migraciones iniciales + permisos mínimos del rol del tenant.
        self.migrate(database)
        logger.info("Base de datos del tenant %s lista", tenant.id)
        return secret_arn

    def migrate(self, database: str) -> str | None:
        """Aplica las migraciones pendientes a una BD de tenant (también la usa migrate_tenants)."""
        engine = create_pg_engine(
            self._settings,
            build_url(self._settings, self._credentials, pg_admin.check_identifier(database)),
            pool_size=None,
        )
        try:
            with engine.begin() as conn:
                revision = upgrade_to_head("tenant", conn)
                self._grant_app_role(conn, role=database)
            return revision
        finally:
            engine.dispose()

    @staticmethod
    def _grant_app_role(conn: Connection, role: str) -> None:
        driver_conn: Any = conn.connection.driver_connection
        with driver_conn.cursor() as cur:
            pg_admin.grant_dml(cur, role, VERSION_TABLES["tenant"])
