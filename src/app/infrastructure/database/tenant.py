from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session


def tenant_session(engine: Engine) -> Iterator[Session]:
    """Sesión ligada a UNA base de datos de tenant. Se cierra siempre, incluso con errores."""
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
