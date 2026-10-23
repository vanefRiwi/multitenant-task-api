from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session

from app.config.settings import Settings
from app.infrastructure.database.credentials import DatabaseCredentials, build_url
from app.infrastructure.database.engine import create_pg_engine


def create_central_engine(settings: Settings, credentials: DatabaseCredentials) -> Engine:
    return create_pg_engine(
        settings,
        build_url(settings, credentials, settings.control_db_name),
        pool_size=settings.central_pool_size,
        max_overflow=settings.central_max_overflow,
    )


def central_session(engine: Engine) -> Iterator[Session]:
    """Una sesión por petición. El commit/rollback vive aquí, no en los repositorios."""
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
