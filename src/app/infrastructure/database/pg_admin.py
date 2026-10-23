"""Sentencias administrativas de PostgreSQL (roles, bases de datos, permisos).

CREATE ROLE / CREATE DATABASE no admiten parámetros (%s), así que los nombres se validan
con una expresión regular estricta y se escapan con psycopg.sql.Identifier, y las
contraseñas con psycopg.sql.Literal. Nunca se concatenan cadenas del cliente.
"""

import re
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.config.settings import Settings
from app.infrastructure.database.credentials import DatabaseCredentials

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def check_identifier(name: str) -> str:
    if not IDENTIFIER.fullmatch(name):
        raise ValueError("Identificador de PostgreSQL inválido")
    return name


def connect(
    settings: Settings, credentials: DatabaseCredentials, database: str
) -> psycopg.Connection[Any]:
    conninfo = make_conninfo(
        host=settings.db_host,
        port=settings.db_port,
        user=credentials.username,
        password=credentials.password,
        dbname=database,
        connect_timeout=settings.db_connect_timeout_seconds,
        application_name="multitenant-task-api-admin",
    )
    return psycopg.connect(conninfo, autocommit=True)


def role_exists(cur: psycopg.Cursor[Any], role: str) -> bool:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    return cur.fetchone() is not None


def database_exists(cur: psycopg.Cursor[Any], database: str) -> bool:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
    return cur.fetchone() is not None


def ensure_role(
    cur: psycopg.Cursor[Any],
    role: str,
    password: str,
    attributes: str,
    connection_limit: int | None = None,
) -> None:
    """Crea el rol o, si ya existe, actualiza su contraseña (idempotente).

    Al actualizar solo se tocan LOGIN, contraseña y límite de conexiones: cambiar
    atributos como NOSUPERUSER exige ser superusuario, y ni el maestro de RDS ni el
    provisionador lo son."""
    check_identifier(role)
    limit = sql.SQL(" CONNECTION LIMIT {}").format(
        sql.Literal(connection_limit if connection_limit is not None else -1)
    )
    if role_exists(cur, role):
        statement = sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}")
    else:
        statement = sql.SQL("CREATE ROLE {} WITH " + attributes + " PASSWORD {}")
    cur.execute(statement.format(sql.Identifier(role), sql.Literal(password)) + limit)


def ensure_database(cur: psycopg.Cursor[Any], database: str) -> None:
    check_identifier(database)
    if not database_exists(cur, database):
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))


def restrict_database(cur: psycopg.Cursor[Any], database: str, allowed_role: str) -> None:
    """Solo `allowed_role` (y el dueño) pueden conectarse a la base de datos."""
    cur.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
    cur.execute(
        sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
            sql.Identifier(database), sql.Identifier(check_identifier(allowed_role))
        )
    )


def grant_dml(cur: psycopg.Cursor[Any], role: str, version_table: str) -> None:
    """Permisos mínimos para la aplicación: leer y escribir filas, nada de DDL.

    Se ejecuta conectado a la base de datos correspondiente, como dueño de sus tablas."""
    ident = sql.Identifier(check_identifier(role))
    statements: list[sql.Composed | sql.SQL] = [
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident),
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
            ident
        ),
        sql.SQL("REVOKE ALL ON TABLE {} FROM {}").format(sql.Identifier(version_table), ident),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(ident),
    ]
    for statement in statements:
        cur.execute(statement)
