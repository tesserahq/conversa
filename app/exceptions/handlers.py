from traceback import format_exc
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.config import get_settings
from app.exceptions.resource_not_found_error import ResourceNotFoundError


def register_exception_handlers(app: FastAPI) -> None:
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
