"""Errores de negocio.

Todas heredan de DomainError. La capa de presentación tiene UN manejador global
que traduce cada `code` a un status HTTP, así los routers no repiten try/except.
"""


class DomainError(Exception):
    code: str = "domain_error"
    default_message: str = "Error de dominio"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class ValidationError(DomainError):
    code = "invalid_request"
    default_message = "La solicitud no es válida"


class AuthenticationError(DomainError):
    code = "not_authenticated"
    default_message = "Credenciales ausentes o inválidas"


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    default_message = "Email o contraseña incorrectos"


class PermissionDeniedError(DomainError):
    code = "permission_denied"
    default_message = "No tienes permiso para realizar esta acción"


class NotFoundError(DomainError):
    code = "not_found"
    default_message = "Recurso no encontrado"


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    default_message = "Usuario no encontrado"


class TenantNotFoundError(NotFoundError):
    # También se usa cuando el tenant existe pero el usuario no es miembro:
    # así no revelamos qué organizaciones existen.
    code = "tenant_not_found"
    default_message = "Organización no encontrada"


class TaskNotFoundError(NotFoundError):
    code = "task_not_found"
    default_message = "Tarea no encontrada"


class MembershipNotFoundError(NotFoundError):
    code = "membership_not_found"
    default_message = "Membresía no encontrada"


class ConflictError(DomainError):
    code = "conflict"
    default_message = "Conflicto con el estado actual del recurso"


class UserAlreadyExistsError(ConflictError):
    code = "user_already_exists"
    default_message = "Ya existe un usuario con ese email"


class TenantSlugAlreadyExistsError(ConflictError):
    code = "tenant_slug_already_exists"
    default_message = "Ya existe una organización con ese slug"


class MembershipAlreadyExistsError(ConflictError):
    code = "membership_already_exists"
    default_message = "El usuario ya pertenece a la organización"


class TenantNotActiveError(ConflictError):
    code = "tenant_not_active"
    default_message = "La organización no está activa"


class LastOwnerError(ConflictError):
    code = "last_owner"
    default_message = "La organización debe conservar al menos un owner"


class ServiceUnavailableError(DomainError):
    code = "service_unavailable"
    default_message = "Una dependencia no está disponible. Inténtalo más tarde"


class TenantProvisioningError(ServiceUnavailableError):
    code = "tenant_provisioning_failed"
    default_message = "No se pudo aprovisionar la base de datos de la organización"
