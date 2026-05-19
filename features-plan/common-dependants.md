# Cross-Module Dependencies Tracking

## Settings: Company / Entity Setup
- **Finance Module:** Relies fundamentally on the `base_currency` field on the entity to execute the `Numeric(20,4)` Money Rule conversions correctly.
- **Global / Core:** Establishes the `subsidiary_id` domain. Every module's row-level security and tenant isolation relies on the existence of these entity records.

## Settings: User Management & RBAC
- **Global / Core:** Manages the `core_users` table which populates the `created_by` column on every `BESBase` record system-wide.
- **Authentication Middleware:** Updates to roles/permissions require the core system to immediately evaluate active JWTs and refresh tokens to prevent unauthorized access.

## Settings: System Audit Log & Activity Trail
- **Global / Core:** Strictly depends on the `core.audit_log`, `core.field_change_log`, and `core.event_store` schema.
- **All Modules:** The value and accuracy of the Audit Explorer depend entirely on downstream modules (Finance, Inventory, CRM) diligently invoking `AuditService.log_action` and passing `correlation_id` contexts during transactions.
