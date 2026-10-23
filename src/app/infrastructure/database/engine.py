from typing import Any

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.pool import NullPool

from app.config.settings import Settings


def create_pg_engine(
    settings: Settings,
    url: URL,
    *,
    pool_size: int | None,
    max_overflow: int = 0,
    autocommit: bool = False,
) -> Engine:
    """Engine con valores seguros para Lambda.

    - hide_parameters: los valores de las consultas no aparecen en errores ni logs.
    - pool_pre_ping: descarta conexiones que RDS cerró mientras la Lambda dormía.
    - pool_size=None => NullPool (sin conexiones retenidas, para tareas puntuales).
    """
    kwargs: dict[str, Any] = {
        "hide_parameters": True,
        "connect_args": {
            "connect_timeout": settings.db_connect_timeout_seconds,
            "application_name": "multitenant-task-api",
        },
    }
    if autocommit:
        kwargs["isolation_level"] = "AUTOCOMMIT"
    if pool_size is None:
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=10,
        )
    return create_engine(url, **kwargs)
