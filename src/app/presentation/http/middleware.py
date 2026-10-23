import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

logger = logging.getLogger("app.requests")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Asigna un request_id (o reutiliza el del cliente si es válido) y registra
    método, ruta, status y duración. No registra cuerpos, cabeceras ni tokens."""
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s (%.1f ms) request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        request_id,
    )
    return response
