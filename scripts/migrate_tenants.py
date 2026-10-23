"""Aplica las migraciones de `migrations/tenant` a TODAS las organizaciones activas.

    uv run python scripts/migrate_tenants.py

Sale con código 1 si algún tenant falla (para que el pipeline lo detecte).
"""

import json
import sys

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.container import build_secret_provider
from app.infrastructure.ops.tenant_migrations import migrate_all_tenants


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    result = migrate_all_tenants(settings, build_secret_provider(settings))
    print(json.dumps(result, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
