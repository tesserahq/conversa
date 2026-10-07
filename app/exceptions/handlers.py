from traceback import format_exc

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.core.completion_output import CompletionFailure
from app.exceptions.resource_not_found_error import ResourceNotFoundError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CompletionFailure)
    async def completion_failure_handler(request: Request, exc: CompletionFailure):
        # Always 502: Modela's own status (e.g. 401 on Conversa's delegated
        # token) describes Conversa's upstream call, not the client's request.
        original = exc.original_error
        details = []
        if not get_settings().is_production:
            details = [
                {
                    "type": original.__class__.__name__,
                    "message": str(original),
                    "upstream_status": getattr(original, "status_code", None),
                }
            ]
        extensions = {"events": [event.model_dump(mode="json") for event in exc.events]}
        if exc.truncations:
            extensions["truncations"] = [
                marker.model_dump(mode="json") for marker in exc.truncations
            ]
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "code": status.HTTP_502_BAD_GATEWAY,
                "message": "Completion failed",
                "details": details,
                "extensions": extensions,
            },
        )

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        raw_message = str(exc).strip() or "Validation error"
        details = getattr(exc, "details", None)
        if details is None:
            details = []
            cause = exc.__cause__
            if isinstance(cause, ValidationError):
                details = [dict(item) for item in cause.errors()]

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "code": status.HTTP_422_UNPROCESSABLE_CONTENT,
                "message": raw_message,
                "details": details,
            },
        )

    @app.exception_handler(Exception)
    async def debug_exception_handler(request: Request, exc: Exception):
        settings = get_settings()
        details = []
        if not settings.is_production:
            details = [
                {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "traceback": format_exc(),
                }
            ]

        return JSONResponse(
            {
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Internal server error",
                "details": details,
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
