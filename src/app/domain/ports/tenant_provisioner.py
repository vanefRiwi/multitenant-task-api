from abc import ABC, abstractmethod

from app.domain.entities.tenant import Tenant


class TenantProvisioner(ABC):
    @abstractmethod
    def provision(self, tenant: Tenant) -> str:
        """Crea (o completa) la base de datos del tenant, su usuario con permisos mínimos,
        el secreto con sus credenciales y aplica las migraciones.

        Debe ser idempotente: si una ejecución anterior falló a mitad, volver a llamarlo
        termina el trabajo. Devuelve la referencia (ARN) del secreto.
        Lanza TenantProvisioningError si algo falla.
        """
