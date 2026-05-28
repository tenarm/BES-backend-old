"""BES Core Kernel — public API surface."""

# --- Data & Session ---
from .database import (
    get_engine,
    get_session_maker,
    get_async_session,
    subsidiary_id_context,
)

# --- Base Models (from models/ package) ---
from .models import (
    BESBase,
    User,
    Role,
    RefreshToken,
    Customer,
    Vendor,
    Product,
    UOM,
)

# --- Notifications ---
from .notifications import (
    NotificationRule,
    Notification,
    NotificationService,
    notification_broadcaster,
)

# --- Auth ---
from .auth import (
    get_current_user,
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

# --- RBAC ---
from .rbac import (
    require_permission,
    get_user_permissions,
    get_simplified_json,
    PERMISSIONS_SCHEMA,
    ExecutionContextType,
    elevate_context,
)

# --- Licensing ---
from .licensing import (
    is_feature_licensed,
    require_licensed_feature,
    LicensingError,
)

# --- Exceptions ---
from .exceptions import (
    DomainException,
    ConcurrencyError,
    ValidationError,
    StateTransitionError,
    EntityNotFoundError,
    InsufficientPermissionError,
)

# --- Repository ---
from .repository import BaseRepository

# --- Responses ---
from .responses import (
    StandardResponse,
    success_response,
    error_response,
    paginated_response,
    setup_exception_handlers,
)

# --- Pagination ---
from .pagination import PaginationParams

# --- Audit ---
from .audit import (
    AuditService,
    AuditLog,
    FieldChangeLog,
    EventStore,
    ImmutableBase,
    audit_broadcaster,
)

# --- Events ---
from .events import (
    event_bus,
    BaseEventPayload,
    AbstractEventBus,
    InMemoryEventBus,
)

# --- Extension Contract ---
from .extension import ExtensionManifest

# --- Middleware ---
from .middleware import (
    RequestLoggingMiddleware,
    ContextAwareSecurityMiddleware,
    correlation_id_context,
    current_user_id_context,
    current_user_name_context,
)

# --- Routers & Seed Utilities (from router/ package) ---
from .router import (
    router as auth_router,
    audit_router,
    notification_router,
    seed_roles,
    seed_admin_user,
    cleanup_expired_tokens,
)

# --- Flow Engine ---
from .flows import (
    FlowPipelineOverride,
    FlowTask,
    FlowEntityLink,
    FlowStep,
    FlowDefinition,
    FlowTaskCreate,
    FlowTaskRead,
    FlowResolver,
    evaluate_condition,
)

# --- Attachments ---
from .attachments import EntityAttachment, AttachmentService

# --- Comments ---
from .comments import EntityComment, CommentService

# --- Number Sequences ---
from .sequences import NumberSequence, SequenceService

# --- Custom Fields ---
from .custom_fields import CustomFieldDefinition, CustomFieldService

# --- Document Generation ---
from .documents import DocumentService


__all__ = [
    # Database
    "get_engine", "get_session_maker", "get_async_session", "subsidiary_id_context",
    # Models
    "BESBase", "User", "Role", "RefreshToken",
    "Customer", "Vendor", "Product", "UOM",
    # Auth
    "get_current_user", "get_password_hash", "verify_password",
    "create_access_token", "create_refresh_token", "decode_token",
    # RBAC
    "require_permission", "get_user_permissions", "get_simplified_json",
    "PERMISSIONS_SCHEMA", "ExecutionContextType", "elevate_context",
    # Licensing
    "is_feature_licensed", "require_licensed_feature", "LicensingError",
    # Exceptions
    "DomainException", "ConcurrencyError", "ValidationError",
    "StateTransitionError", "EntityNotFoundError", "InsufficientPermissionError",
    # Repository
    "BaseRepository",
    # Responses
    "StandardResponse", "success_response", "error_response",
    "paginated_response", "setup_exception_handlers",
    # Pagination
    "PaginationParams",
    # Audit
    "AuditService", "AuditLog", "FieldChangeLog", "EventStore",
    "ImmutableBase", "audit_broadcaster",
    # Events
    "event_bus", "BaseEventPayload", "AbstractEventBus", "InMemoryEventBus",
    # Extension
    "ExtensionManifest",
    # Middleware
    "RequestLoggingMiddleware", "ContextAwareSecurityMiddleware",
    "correlation_id_context", "current_user_id_context", "current_user_name_context",
    # Routers & Seeds
    "auth_router", "audit_router", "notification_router",
    "seed_roles", "seed_admin_user", "cleanup_expired_tokens",
    # Notifications
    "NotificationRule", "Notification", "NotificationService", "notification_broadcaster",
    # Flows
    "FlowPipelineOverride", "FlowTask", "FlowEntityLink",
    "FlowStep", "FlowDefinition", "FlowTaskCreate", "FlowTaskRead",
    "FlowResolver", "evaluate_condition",
    # Attachments
    "EntityAttachment", "AttachmentService",
    # Comments
    "EntityComment", "CommentService",
    # Sequences
    "NumberSequence", "SequenceService",
    # Custom Fields
    "CustomFieldDefinition", "CustomFieldService",
    # Documents
    "DocumentService",
]