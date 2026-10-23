"""Preparación de control_db: roles, base de datos, migraciones centrales y permisos.

Usa la credencial de administrador (en AWS, el usuario maestro de RDS). Es idempotente:
se puede ejecutar en cada despliegue."""

import logging
from typing import Any

from app.config.settings import Settings
from app.infrastructure.database import pg_admin
from app.infrastructure.database.credentials import (
    admin_credentials,
    build_url,
    central_credentials,
    provisioner_credentials,
)
from app.infrastructure.database.engine import create_pg_engine
from app.infrastructure.database.migrations import VERSION_TABLES, upgrade_to_head
from app.infrastructure.secrets.secret_provider import SecretProvider

logger = logging.getLogger(__name__)

APP_ROLE_ATTRIBUTES = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"
PROVISIONER_ROLE_ATTRIBUTES = "LOGIN NOSUPERUSER CREATEDB CREATEROLE"


def bootstrap_control_plane(settings: Settings, secrets: SecretProvider) -> dict[str, Any]:
    admin = admin_credentials(settings, secrets)
    central = central_credentials(settings, secrets)
    provisioner = provisioner_credentials(settings, secrets)
    control_db = pg_admin.check_identifier(settings.control_db_name)

    with (
        pg_admin.connect(settings, admin, settings.maintenance_db_name) as admin_conn,
        admin_conn.cursor() as cur,
    ):
        pg_admin.ensure_role(cur, central.username, central.password, APP_ROLE_ATTRIBUTES)
        pg_admin.ensure_role(
            cur, provisioner.username, provisioner.password, PROVISIONER_ROLE_ATTRIBUTES
        )
        pg_admin.ensure_database(cur, control_db)
        pg_admin.restrict_database(cur, control_db, central.username)

    engine = create_pg_engine(settings, build_url(settings, admin, control_db), pool_size=None)
    try:
        with engine.begin() as conn:
            revision = upgrade_to_head("central", conn)
            driver_conn: Any = conn.connection.driver_connection
            with driver_conn.cursor() as cur:
                pg_admin.grant_dml(cur, central.username, VERSION_TABLES["central"])
    finally:
        engine.dispose()

    logger.info("control_db lista en la revisión %s", revision)
    return {"control_db": control_db, "central_revision": revision}
