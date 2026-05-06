from typing import Any, Optional, Dict
from pydantic import BaseModel
from fastapi import Request, FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

class StandardResponse(BaseModel):
    status: str
    data: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

def success_response(data: Any, metadata: Optional[Dict[str, Any]] = None) -> StandardResponse:
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

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response(f"Validation Error: {exc.errors()}").model_dump()
        )
