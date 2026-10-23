"""Reintenta la provisión de un tenant que quedó en estado 'failed' o 'provisioning'.

uv run python scripts/provision_tenant.py <tenant_id>
"""

import argparse
import json
import sys
from uuid import UUID

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.domain.exceptions import DomainError
from app.infrastructure.container import build_secret_provider
from app.infrastructure.ops.provisioning import retry_tenant_provisioning


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant_id", type=UUID)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        result = retry_tenant_provisioning(
            settings, build_secret_provider(settings), args.tenant_id
        )
    except DomainError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
