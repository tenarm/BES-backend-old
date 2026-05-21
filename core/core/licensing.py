import logging
from fastapi import HTTPException, status
from core.rbac import PERMISSIONS_SCHEMA, execution_context, ExecutionContextType

logger = logging.getLogger(__name__)

class LicensingError(Exception):
    """Bespoke exception raised when a client attempts to access a feature outside their package tier."""
    pass

def is_feature_licensed(module: str, subfeature: str) -> bool:
    """
    Checks if a specific sub-feature is licensed based on the active client schema.
    
    Bypasses checks if:
    1. The execution context is ExecutionContextType.SYSTEM.
    2. The module is 'core' (always allowed).
    """
    if execution_context.get() == ExecutionContextType.SYSTEM:
        return True

    if module == "core":
        return True

    # Check if the module exists in the client's admin permissions schema
    module_schema = PERMISSIONS_SCHEMA.get(module)
    if not module_schema:
        logger.debug(f"Module '{module}' is not present in client PERMISSIONS_SCHEMA.")
        return False

    # Check if the granular sub-feature is present
    if subfeature not in module_schema:
        logger.debug(f"Sub-feature '{module}:{subfeature}' is not present in client PERMISSIONS_SCHEMA.")
        return False

    return True

def require_licensed_feature(module: str, subfeature: str):
    """
    Asserts that a sub-feature is licensed.
    
    If the check fails, raises:
    1. HTTPException (HTTP 403) to automatically respond to web API requests.
    2. LicensingError for internal non-web service contexts.
    """
    if not is_feature_licensed(module, subfeature):
        err_msg = f"Subscription Restriction: Feature '{module}:{subfeature}' is not licensed under your current package tier."
        logger.warning(err_msg)
        
        # Raise standard FastAPI HTTPException to automatically generate 403 Forbidden
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_msg
        )
