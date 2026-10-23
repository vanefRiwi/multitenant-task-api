"""Ejecución programática de Alembic (la usan la provisión de tenants y los procesos operativos).

Las migraciones nunca se ejecutan al arrancar la Lambda de la API: solo desde la
provisión de un tenant nuevo, los scripts de `scripts/` o la Lambda de operaciones.
"""

import os
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

Kind = Literal["central", "tenant"]
VERSION_TABLES: dict[Kind, str] = {
    "central": "alembic_version_central",
    "tenant": "alembic_version_tenant",
}


def project_root() -> Path:
    """Carpeta que contiene alembic-*.ini y migrations/.

    En desarrollo es la raíz del repo; en Lambda es la raíz del paquete desplegado."""
    override = os.environ.get("APP_MIGRATIONS_ROOT")
    candidates = [Path(override)] if override else []
    candidates += list(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "alembic-tenant.ini").exists() and (candidate / "migrations").is_dir():
            return candidate
    raise RuntimeError("No se encontró la carpeta de migraciones")


def alembic_config(kind: Kind, connection: Connection | None = None) -> Config:
    root = project_root()
    config = Config(str(root / f"alembic-{kind}.ini"))
    config.set_main_option("script_location", str(root / "migrations" / kind))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade_to_head(kind: Kind, connection: Connection) -> str | None:
    command.upgrade(alembic_config(kind, connection), "head")
    return current_revision(kind, connection)


def current_revision(kind: Kind, connection: Connection) -> str | None:
    context = MigrationContext.configure(connection, opts={"version_table": VERSION_TABLES[kind]})
    return context.get_current_revision()


def head_revision(kind: Kind) -> str | None:
    return ScriptDirectory.from_config(alembic_config(kind)).get_current_head()
