import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"


class ConfigurationError(AppError):
    status_code = 503
    code = "configuration_error"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "detail": "Request validation failed.",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "detail": "Validation failed.",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception error=%s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "detail": "An unexpected error occurred.",
            },
        )
