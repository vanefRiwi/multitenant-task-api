from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.config.settings import Settings
from app.infrastructure.container import build_secret_provider
from app.infrastructure.database.credentials import admin_credentials, build_url
from app.infrastructure.database.migrations import VERSION_TABLES
from app.infrastructure.models.central import central_metadata

config = context.config
external_connection = config.attributes.get("connection")

if external_connection is None and config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = central_metadata
VERSION_TABLE = VERSION_TABLES["central"]


def _url() -> str:
    settings = Settings()
    credentials = admin_credentials(settings, build_secret_provider(settings))
    return build_url(settings, credentials, settings.control_db_name).render_as_string(
        hide_password=False
    )


def _configure(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if external_connection is not None:
        _configure(external_connection)
        return
    engine = create_engine(_url(), poolclass=NullPool)
    with engine.begin() as connection:
        _configure(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
