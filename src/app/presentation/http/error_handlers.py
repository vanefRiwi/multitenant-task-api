"""Manejador global de errores: un solo lugar traduce excepciones a HTTP.

Formato uniforme:
    {"error": {"code": "...", "message": "...", "request_id": "...", "details": [...]}}

Nunca se devuelven trazas, SQL, contraseñas ni nombres internos (bases de datos, ARNs).
En los logs solo se registra el tipo de excepción y el request_id.
"""

import logging
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)

logger = logging.getLogger("app.errors")

DOMAIN_STATUS: list[tuple[type[DomainError], int]] = [
    (ValidationError, status.HTTP_400_BAD_REQUEST),
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
    (PermissionDeniedError, status.HTTP_403_FORBIDDEN),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (ServiceUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE),
]

HTTP_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "too_many_requests",
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": _request_id(request),
    }
    if details:
        body["details"] = details
    response_headers = dict(headers or {})
    if (request_id := _request_id(request)) is not None:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse({"error": body}, status_code=status_code, headers=response_headers)


def status_for(exc: DomainError) -> int:
    for exc_type, code in DOMAIN_STATUS:
        if isinstance(exc, exc_type):
            return code
    return status.HTTP_400_BAD_REQUEST


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(DomainError, exc)
    status_code = status_for(exc)
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    if status_code >= 500:
        logger.warning(
            "Dependencia no disponible: %s (request_id=%s, causa=%s)",
            exc.code,
            _request_id(request),
            type(exc.__cause__).__name__ if exc.__cause__ else None,
        )
    return error_response(request, status_code, exc.code, exc.message, headers=headers)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    # Solo ubicación, mensaje y tipo: NO se devuelve el valor enviado (`input`),
    # que podría ser una contraseña.
    details = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Los datos enviados no son válidos",
        details=details,
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    code = HTTP_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Error HTTP"
    headers = dict(exc.headers) if exc.headers else None
    return error_response(request, exc.status_code, code, message, headers=headers)


async def database_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Base de datos no disponible (%s, request_id=%s)",
        type(exc).__name__,
        _request_id(request),
    )
    return error_response(
        request,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "service_unavailable",
        ServiceUnavailableError.default_message,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Error no controlado (%s, request_id=%s)", type(exc).__name__, _request_id(request)
    )
    return error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Error interno del servidor",
    )


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, OperationalError | InterfaceError):
        return await database_unavailable_handler(request, exc)
    return await unhandled_error_handler(request, exc)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(DBAPIError, database_error_handler)
    app.add_exception_handler(PoolTimeoutError, database_unavailable_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
