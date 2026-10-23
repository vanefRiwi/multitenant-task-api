"""Inspección de solo lectura: qué bases de datos de tenant existen y qué contiene cada una.

Existe para poder VER el aislamiento sin acceso directo a RDS (está en una red privada):
se invoca desde la consola de Lambda con {"action": "inspect_tenants"}. No modifica nada
y nunca devuelve contraseñas.
"""

import logging
from typing import Any

import psycopg
from sqlalchemy import text
from sqlmodel import Session

from app.config.settings import Settings
from app.domain.entities.tenant import Tenant
from app.infrastructure.database import pg_admin
from app.infrastructure.database.central import create_central_engine
from app.infrastructure.database.credentials import (
    DatabaseCredentials,
    central_credentials,
    provisioner_credentials,
)
from app.infrastructure.repositories.sqlmodel_tenant_repository import SqlModelTenantRepository
from app.infrastructure.secrets.secret_provider import SecretProvider
from app.infrastructure.tenancy.tenant_database_factory import TenantDatabaseFactory

logger = logging.getLogger(__name__)


def inspect_tenants(settings: Settings, secrets: SecretProvider) -> dict[str, Any]:
    engine = create_central_engine(settings, central_credentials(settings, secrets))
    try:
        with Session(engine) as session:
            tenants = SqlModelTenantRepository(session).list_all()
    finally:
        engine.dispose()

    databases = _list_databases(settings, provisioner_credentials(settings, secrets))
    factory = TenantDatabaseFactory(settings, secrets)
    try:
        report = [_describe(factory, tenant, databases) for tenant in tenants]
    finally:
        factory.dispose_all()

    return {
        "bases_de_datos_en_rds": databases,
        "tenants_en_control_db": report,
        "prueba_cruzada": _cross_access_check(settings, secrets, tenants),
    }


def _list_databases(settings: Settings, credentials: DatabaseCredentials) -> list[str]:
    with (
        pg_admin.connect(settings, credentials, settings.maintenance_db_name) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            "SELECT datname FROM pg_database"
            " WHERE datname = %s OR datname LIKE %s ORDER BY datname",
            (settings.control_db_name, f"{settings.tenant_db_prefix}%"),
        )
        return [row[0] for row in cur.fetchall()]


def _describe(
    factory: TenantDatabaseFactory, tenant: Tenant, databases: list[str]
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status.value,
        "database_name": tenant.database_name,
        "secret_arn": tenant.secret_arn,
        "base_existe": tenant.database_name in databases,
    }
    if not tenant.is_active:
        return entry
    try:
        # Se conecta con el usuario PROPIO del tenant, leído de su secreto.
        with factory.get_engine(tenant).connect() as conn:
            entry["conectado_como"] = conn.execute(text("SELECT current_user")).scalar()
            entry["tareas"] = conn.execute(text("SELECT count(*) FROM tasks")).scalar()
            entry["titulos"] = list(
                conn.execute(text("SELECT title FROM tasks ORDER BY created_at LIMIT 5")).scalars()
            )
    except Exception as exc:
        logger.error("No se pudo inspeccionar el tenant %s (%s)", tenant.id, type(exc).__name__)
        entry["error"] = type(exc).__name__
    return entry


def _cross_access_check(
    settings: Settings, secrets: SecretProvider, tenants: list[Tenant]
) -> dict[str, Any]:
    """Intenta abrir la base de un tenant con las credenciales de otro: debe fallar."""
    active = [t for t in tenants if t.is_active and t.secret_arn]
    if len(active) < 2:
        return {"resultado": "se necesitan al menos 2 tenants activos"}
    owner, target = active[0], active[1]
    data = secrets.get_json(str(owner.secret_arn))
    credentials = DatabaseCredentials(username=data["username"], password=data["password"])
    try:
        with pg_admin.connect(settings, credentials, target.database_name):
            result = "ACCESO PERMITIDO (no debería pasar)"
    except psycopg.OperationalError as exc:
        denied = "permission denied" in str(exc)
        result = "acceso denegado por PostgreSQL" if denied else "no se pudo comprobar"
    return {
        "usuario": owner.database_name,
        "de_la_organizacion": owner.slug,
        "intenta_abrir": target.database_name,
        "de_la_organizacion_destino": target.slug,
        "resultado": result,
    }
