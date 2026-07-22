"""Typed application exceptions + FastAPI handler registration.

Modules raise these instead of constructing ``HTTPException`` inline so that
status codes and response shapes stay consistent platform-wide.

Conventions (docs/product-plan/PRODUCT_PLAN.md §11):
- Scope violations surface as 404 (``NotFoundError``), never 403, so the API
  does not leak resource existence across OrgUnit subtrees.
- Every error body is ``{"detail": <message>}`` — the same shape FastAPI's
  default ``HTTPException`` handler produces, so existing frontend error
  handling keeps working during the migration.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for all typed application errors."""

    status_code = 500
    default_detail = "Internal server error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """Resource missing OR outside the caller's OrgUnit scope (404-not-403)."""

    status_code = 404
    default_detail = "Resource not found"


class PermissionDeniedError(AppError):
    """Explicit 403 — only for role-gate failures where existence is public
    (e.g. a Member calling a PlatformAdmin endpoint)."""

    status_code = 403
    default_detail = "Permission denied"


class ValidationError(AppError):
    status_code = 422
    default_detail = "Invalid input"


class ConflictError(AppError):
    status_code = 409
    default_detail = "Conflict with existing resource"


class ExternalServiceError(AppError):
    """Upstream dependency (LLM, S3, email) failed after retries."""

    status_code = 502
    default_detail = "Upstream service unavailable"


def register_error_handlers(app: FastAPI) -> None:
    """Attach one JSON handler for the whole AppError family."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
