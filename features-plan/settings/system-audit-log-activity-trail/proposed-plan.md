## 1. Feature & Scope
The "System Audit Log & Activity Trail" feature provides a unified, cross-module ledger of all business actions, mutations, and system events. It leverages the existing `ImmutableBase` core tables (`core.audit_log`, `core.field_change_log`, `core.event_store`) to expose detailed entity timelines, field-level diffs, and cross-module business data lineage to authorized administrators via a comprehensive UI.

## 2. Architectural Compliance Sign-off
- [x] **Immutable Data Model**: Correctly acknowledges and uses `ImmutableBase` instead of standard `BESBase` (ensuring no soft deletes or silent updates).
- [x] **Hub-and-Spoke MDM**: Perfectly aligns with the pattern; no module-specific spoke tables are created. The `settings` module acts purely as a viewer/controller for the central `core` hub data.
- [x] **Process Transparency UI**: Heavy adoption of `@bes/shared-ui` components (`Timeline`, `ProcessPipeline`) to expose system internals visually.
- [x] **Money Rule**: N/A for audit log entries structurally, but financial JSON payloads will inherently reflect the `Numeric(20,4)` values captured by source modules.
- [x] **RBAC**: Handled correctly; mapped to `settings:audit_log:read` and `write`, explicitly preventing `delete` actions at the system level regardless of JSON config.

## 3. Cross-Module Dependencies
- **Core Dependency**: The feature relies entirely on the pre-existing `core` audit schema and the `AuditService`.
- **Global Data Feeder**: The value of this dashboard is completely dependent on every other module (Finance, Sales, etc.) properly invoking `AuditService.log_action` and persisting `correlation_id` context throughout multi-stage transactions.

## 4. Implementation Sequence

**Phase 1: Backend API Exposure (Settings Module)**
- Implement `GET /api/v1/settings/audit-logs` endpoint with advanced filtering and pagination.
- Implement `GET /api/v1/settings/audit-logs/{id}` to fetch an event with its nested `field_change_log` entries.
- Wire up `GET /api/v1/settings/audit-logs/entity/{entity_type}/{entity_id}` directly to `AuditService.get_entity_timeline()`.
- Wire up `GET /api/v1/settings/audit-logs/correlation/{correlation_id}` directly to `AuditService.get_correlation_chain()`.

**Phase 2: UI Foundation & Global Ledger (Frontend)**
- Create the main `/settings/audit-log` route in the `settings` module frontend library.
- Build the advanced filter bar (Date ranges, Module selects, Action type filters).
- Implement the paginated `DataTable` to display the global activity ledger safely.

**Phase 3: Drawer & Process Inspectors (Frontend)**
- Build the `Audit Event Details` Drawer with its 4 functional tabs (Summary, Field Mutations, Data Lineage, Entity Timeline).
- Build the custom tabular diff viewer for Field Mutations (old value vs. new value).
- Wire up the `ProcessPipeline` component for the Data Lineage/Correlation tab.
- Wire up the `Timeline` component for the Entity Timeline tab.

**Phase 4: Export Engine (Backend Worker)**
- Implement the `POST /api/v1/settings/audit-logs/export` endpoint.
- Register a background worker to handle the `AUDIT_LOG_EXPORT_REQUESTED` event, compiling the filtered datasets into CSV/PDF and sending secure download links.
