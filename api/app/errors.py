"""ApiError + exception handlers → `{ error: { code, message, details? } }` (06 §C).

Codes are strings so business rules can add their own (`seat_taken`, `hold_missing`,
`has_sales`, `too_many_seats`); the generic ones and their statuses live in `STATUS_FOR_CODE`.
"""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

STATUS_FOR_CODE: dict[str, int] = {
    "validation": 422,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "rate_limited": 429,
    "unavailable": 503,
    "internal": 500,
}
CODE_FOR_STATUS: dict[int, str] = {status: code for code, status in STATUS_FOR_CODE.items()}

INTERNAL_MESSAGE = "Internal server error"


class ApiError(Exception):
    """Raise from a router or service; the handler renders the envelope.

    `status` defaults from the code; business codes pass it explicitly
    (`ApiError("seat_taken", "…", status=409, details={"taken": [...]})`).
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status or STATUS_FOR_CODE[code]
        self.details = details


def envelope(
    code: str,
    message: str,
    *,
    status: int | None = None,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        {"error": error}, status_code=status or STATUS_FOR_CODE[code], headers=headers
    )


def field_errors_from(exc: RequestValidationError) -> dict[str, str]:
    """`("body", "tiers", 2, "price_paise")` → `"tiers.2.price_paise"`; first message per path."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(part) for part in err["loc"]]
        if err.get("type") == "json_invalid":
            path = "body"
        else:
            path = ".".join(loc[1:]) if len(loc) > 1 else ".".join(loc)
        errors.setdefault(path, str(err["msg"]))
    return errors


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return envelope(exc.code, exc.message, status=exc.status, details=exc.details)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return envelope(
        "validation", "Request validation failed", details={"fields": field_errors_from(exc)}
    )


async def _http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = exc.status_code
    if status == 405:
        return envelope("not_found", "Not Found")
    if status >= 500:
        log.error("HTTPException %s: %s", status, exc.detail)
        return envelope("internal", INTERNAL_MESSAGE)
    code = CODE_FOR_STATUS.get(status, "validation")
    return envelope(code, str(exc.detail), status=status, headers=exc.headers)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    request_id: str | None = getattr(request.state, "request_id", None)
    log.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    headers = {"X-Request-Id": request_id} if request_id else None
    return envelope("internal", INTERNAL_MESSAGE, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(Exception, _unhandled)
    _document_error_contract(app)


def _document_error_contract(app: FastAPI) -> None:
    """Every operation gets the envelope as its `default` response and FastAPI's automatic
    `422 HTTPValidationError` is removed — validation failures are the envelope too."""
    from app.schemas.errors import ApiErrorResponse

    app.router.responses["default"] = {
        "model": ApiErrorResponse,
        "description": "Error envelope (06 §C)",
    }

    original = app.openapi

    def openapi() -> dict[str, Any]:
        schema = original()
        for methods in schema.get("paths", {}).values():
            for op in methods.values():
                op.get("responses", {}).pop("422", None)
        components = schema.get("components", {}).get("schemas", {})
        components.pop("HTTPValidationError", None)
        components.pop("ValidationError", None)
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
