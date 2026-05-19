## 1. Module & Feature Name
- **Module**: Settings
- **Feature Name**: System Audit Log & Activity Trail

## 2. Database Schema (YAML)
Because Audit Logging is a universal requirement, these tables already reside in the `core` schema and inherit from `ImmutableBase` (no `is_deleted`, no `updated_at`). The Settings module interacts with these existing tables.

```yaml
tables:
  - name: audit_log
    schema: core
    description: "Immutable record of every business action in the BES."
    columns:
      - name: id
        type: UUID
        primary_key: true
      - name: created_at
        type: TIMESTAMP
      - name: entity_type
        type: VARCHAR
        index: true
      - name: entity_id
        type: VARCHAR
        index: true
      - name: action
        type: VARCHAR
        index: true
      - name: actor_id
        type: VARCHAR
        nullable: true
      - name: actor_name
        type: VARCHAR
      - name: actor_type
        type: VARCHAR # 'user' | 'system'
      - name: module
        type: VARCHAR
        index: true
      - name: correlation_id
        type: VARCHAR
        index: true
        nullable: true
      - name: description
        type: VARCHAR
      - name: changes
        type: JSONB
      - name: event_id
        type: VARCHAR
        nullable: true
      - name: parent_audit_id
        type: VARCHAR
        nullable: true

  - name: field_change_log
    schema: core
    description: "Detailed before/after snapshot of individual field mutations."
    columns:
      - name: id
        type: UUID
        primary_key: true
      - name: created_at
        type: TIMESTAMP
      - name: audit_log_id
        type: UUID
        foreign_key: core.audit_log.id
        index: true
      - name: entity_type
        type: VARCHAR
      - name: entity_id
        type: VARCHAR
      - name: field_name
        type: VARCHAR
      - name: old_value
        type: TEXT
        nullable: true
      - name: new_value
        type: TEXT
        nullable: true
```

## 3. Hub-and-Spoke MDM Mapping
- **Core Hub Entities**: This feature maps directly to the `audit_log`, `field_change_log`, and `event_store` entities existing centrally within the `core` architecture.
- **Spoke Extension**: There are no local module spoke tables for Audit Logs. The Settings module simply acts as the administrative read-only interface and reporting engine for the central core tables.

## 4. REST APIs
The following APIs wrap the internal `AuditService` methods to expose data to the frontend, conforming to the standard API envelope `{ status, data, metadata, error }`.

- **`GET /api/v1/settings/audit-logs`**
  - **Purpose**: Retrieve the paginated master ledger of audit events.
  - **Query Params**: `page`, `page_size`, `module`, `action`, `actor_id`, `start_date`, `end_date`.
  - **Response Payload**: `data` array contains `AuditLog` records (excluding heavy JSON payloads for list views).

- **`GET /api/v1/settings/audit-logs/{id}`**
  - **Purpose**: Get granular details of a specific audit event, including field mutations.
  - **Response Payload**: `data` contains `AuditLog` + nested `field_changes` array from `field_change_log`.

- **`GET /api/v1/settings/audit-logs/entity/{entity_type}/{entity_id}`**
  - **Purpose**: Powers the frontend `Timeline` component. Wraps `AuditService.get_entity_timeline()`.
  - **Response Payload**: `data` array contains chronological audit events for the specific record.

- **`GET /api/v1/settings/audit-logs/correlation/{correlation_id}`**
  - **Purpose**: Powers the frontend `ProcessPipeline` data lineage view. Wraps `AuditService.get_correlation_chain()`.
  - **Response Payload**: `data` array contains causally linked audit and event records.

- **`POST /api/v1/settings/audit-logs/export`**
  - **Purpose**: Request an asynchronous report generation (CSV/PDF) of filtered audit logs.
  - **Request Payload**: `{ filters: {...}, format: "csv" | "pdf" }`

## 5. Pub/Sub Events
The core `AuditService` uses an internal SSE Broadcaster for real-time UI updates, but for durable messaging related to this feature:

- `AUDIT_LOG_EXPORT_REQUESTED`: Emitted when an administrator requests a large export, triggering a background worker to generate the file and email the secure link.

## 6. RBAC Permissions
These permissions map directly to the `settings.audit_log` resource in `admin_permissions.json`:

- `settings:audit_log:read`: Required to access the Audit Explorer dashboard, view entity timelines, and inspect field mutations.
- `settings:audit_log:write`: Required to initiate Audit Log Exports or configure retention policies (data itself cannot be modified).
- `settings:audit_log:delete`: *(System-level restriction)* Even if granted in JSON, the `ImmutableBase` architecture prevents physical deletion. Only authorized system archiving scripts bypass this limitation.
