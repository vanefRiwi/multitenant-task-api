"""Prepara control_db: crea roles (app_central, tenant_provisioner), la base de datos,
aplica las migraciones centrales y los permisos mínimos. Es idempotente.

    uv run python scripts/bootstrap_database.py
"""

import json

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.container import build_secret_provider
from app.infrastructure.ops.bootstrap import bootstrap_control_plane


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    result = bootstrap_control_plane(settings, build_secret_provider(settings))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
