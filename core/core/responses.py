from typing import Optional, Any
from pydantic import BaseModel
from fastapi import Request, FastAPI, status, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .exceptions import ConcurrencyError
import logging

logger = logging.getLogger(__name__)


class StandardResponse(BaseModel):
    status: str
    data: Optional[Any] = None
    metadata: Optional[dict[str, Any]] = None
    error: Optional[str] = None


def success_response(data: Any, metadata: Optional[dict[str, Any]] = None) -> StandardResponse:
    return StandardResponse(
        status="success",
        data=data,
        metadata=metadata,
        error=None
    )


def error_response(error_msg: str) -> StandardResponse:
    return StandardResponse(
        status="error",
        data=None,
        metadata=None,
        error=error_msg
    )


def paginated_response(
    data: Any,
    total: int,
    page: int,
    page_size: int
) -> StandardResponse:
    """Wraps data with pagination metadata in the standard envelope."""
    return StandardResponse(
        status="success",
        data=data,
        metadata={
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
        },
        error=None
    )


def setup_exception_handlers(app: FastAPI):
    """
    Registers global exception handlers on the FastAPI application
    to ensure all errors conform to the StandardResponse envelope.
    """
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("Internal Server Error").model_dump()
        )

    @app.exception_handler(ConcurrencyError)
    async def concurrency_exception_handler(request: Request, exc: ConcurrencyError):
        logger.warning(f"Concurrency conflict: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_response(exc.message).model_dump()
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTPException caught: {exc.detail} (status: {exc.status_code})")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.detail).model_dump()
        )


    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response(f"Validation Error: {exc.errors()}").model_dump()
        )

