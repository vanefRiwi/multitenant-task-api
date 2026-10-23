from typing import Any

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    # extra="forbid": un campo desconocido (p. ej. "database_name") produce 422 en vez de
    # ignorarse en silencio. El cliente no puede colar parámetros internos.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
