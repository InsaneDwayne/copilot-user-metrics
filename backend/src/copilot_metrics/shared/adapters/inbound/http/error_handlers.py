"""The one place where errors become HTTP responses.

Every error body has the same shape, ``{"code": ..., "detail": ...}``, whether it
comes from a domain error, request validation, an unknown route or a bug.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from copilot_metrics.shared.adapters.inbound.http.middleware import USER_KEY
from copilot_metrics.shared.errors import AccessDenied, DomainError, InvalidRequest, NotAuthenticated, NotFound
from copilot_metrics.shared.kernel import Frozen

log = logging.getLogger(__name__)

# Most specific first; the first matching category wins.
_STATUS_BY_CATEGORY: tuple[tuple[type[DomainError], int], ...] = (
    (NotAuthenticated, status.HTTP_401_UNAUTHORIZED),
    (AccessDenied, status.HTTP_403_FORBIDDEN),
    (NotFound, status.HTTP_404_NOT_FOUND),
    (InvalidRequest, status.HTTP_422_UNPROCESSABLE_CONTENT),
)


class ErrorBody(Frozen):
    code: str
    detail: str


def status_for(error: DomainError) -> int:
    return next((code for kind, code in _STATUS_BY_CATEGORY if isinstance(error, kind)), status.HTTP_400_BAD_REQUEST)


def _respond(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(ErrorBody(code=code, detail=detail).model_dump(), status_code=status_code)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        if isinstance(exc, AccessDenied):  # a signed-in person asked for something their role doesn't allow
            who = request.session.get(USER_KEY, {}).get("login") if "session" in request.scope else None
            log.warning("access denied (%s): %r on %s %s", exc.code, who, request.method, request.url.path)
        return _respond(status_for(exc), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        where = ".".join(str(part) for part in first.get("loc", ()) if part not in ("query", "path", "body"))
        message = first.get("msg", "Invalid request")
        return _respond(
            status.HTTP_422_UNPROCESSABLE_CONTENT, InvalidRequest.code, f"{where}: {message}" if where else message
        )

    @app.exception_handler(StarletteHTTPException)
    async def framework_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Errors Starlette raises itself (unknown route, wrong method)."""
        code = NotFound.code if exc.status_code == status.HTTP_404_NOT_FOUND else "http_error"
        return _respond(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return _respond(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Something went wrong")
