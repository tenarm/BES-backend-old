"""
Core domain exceptions for the BES platform.

Services raise these exceptions; routers catch and translate them
into appropriate HTTP responses via FastAPI exception handlers.
"""


class DomainException(Exception):
    """Base for all business logic errors. Services raise these, routers catch and translate."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ConcurrencyError(DomainException):
    """Raised when a concurrent update/edit conflict is detected (stale data)."""
    def __init__(self, message: str = "Record was modified by another user"):
        super().__init__(message, code="CONCURRENCY_CONFLICT")


class ValidationError(DomainException):
    """Raised when business-level validation fails (not Pydantic schema validation)."""
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")


class StateTransitionError(DomainException):
    """Raised when an invalid status transition is attempted on a state-machine entity."""
    def __init__(self, entity: str, from_status: str, to_status: str):
        self.entity = entity
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"{entity} cannot transition from '{from_status}' to '{to_status}'",
            code="INVALID_TRANSITION"
        )


class EntityNotFoundError(DomainException):
    """Raised when a requested entity does not exist or is soft-deleted."""
    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(
            f"{entity_type} with id '{entity_id}' not found",
            code="NOT_FOUND"
        )


class InsufficientPermissionError(DomainException):
    """Raised when a user lacks the required permission for an action."""
    def __init__(self, permission: str):
        self.permission = permission
        super().__init__(
            f"Missing required permission: {permission}",
            code="PERMISSION_DENIED"
        )
