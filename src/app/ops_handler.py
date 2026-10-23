"""Lambda de operaciones: migraciones controladas y provisión.

NO está expuesta en API Gateway. El pipeline la invoca después de cada despliegue:
    aws lambda invoke --function-name <OpsFunction> --payload '{"action": "bootstrap"}' out.json

Acciones:
- bootstrap: roles, control_db, migraciones centrales y permisos (idempotente).
- migrate_tenants: migraciones de tenant en todas las organizaciones activas.
- provision_tenant: reintenta la provisión de {"tenant_id": "..."}.
- status: revisión actual vs. head (central).
- inspect_tenants: solo lectura; lista las bases de tenant y cuántas tareas tiene cada una.
"""

import logging
from typing import Any
from uuid import UUID

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.container import build_secret_provider
from app.infrastructure.database.migrations import head_revision
from app.infrastructure.ops.bootstrap import bootstrap_control_plane
from app.infrastructure.ops.inspect_tenants import inspect_tenants
from app.infrastructure.ops.provisioning import retry_tenant_provisioning
from app.infrastructure.ops.tenant_migrations import migrate_all_tenants

logger = logging.getLogger(__name__)


class OperationFailedError(Exception):
    pass


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    settings = get_settings()
    configure_logging(settings.log_level)
    secrets = build_secret_provider(settings)
    action = event.get("action")
    logger.info("Operación solicitada: %s", action)

    if action == "bootstrap":
        return bootstrap_control_plane(settings, secrets)
    if action == "migrate_tenants":
        result = migrate_all_tenants(settings, secrets)
        if result["failed"]:
            # Lanzar hace que `aws lambda invoke` devuelva FunctionError y el pipeline falle.
            raise OperationFailedError(f"{len(result['failed'])} tenant(s) sin migrar: {result}")
        return result
    if action == "provision_tenant":
        return retry_tenant_provisioning(settings, secrets, UUID(str(event["tenant_id"])))
    if action == "status":
        return {"central_head": head_revision("central"), "tenant_head": head_revision("tenant")}
    if action == "inspect_tenants":
        return inspect_tenants(settings, secrets)
    raise ValueError(f"Acción desconocida: {action!r}")
