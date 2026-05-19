# 1. Feature & Scope
**Feature:** Company / Entity Setup
**Scope:** Building the hierarchical corporate entity structure (`settings_entities`) to serve as the master data hub for the multi-tenant `subsidiary_id` context. This includes the database schema, tree-based navigation UI, and backend APIs for managing root, subsidiaries, and branches.

# 2. Architectural Compliance Sign-off
- [x] **Hub-and-Spoke MDM:** `settings_entities` serves as the core master context for `subsidiary_id` across all modules.
- [x] **BESBase Heritage:** Table inherits standard `id`, `created_at`, `is_deleted`, `metadata_` columns.
- [x] **Money Rule:** Explicitly manages `base_currency`, which is foundational for the `Numeric(20,4)` Money Rule operations in the Finance module.
- [x] **Soft Deletes:** Deletions set `is_deleted=True` and `status='Suspended'`. Active child entities automatically block parent suspension.
- [x] **UI Degradation:** The UI plan correctly degrades to non-interactive mode for `READONLY_EXTENSIONS`.
- [x] **Shared UI:** Uses `@bes/shared-ui` components (`ProcessPipeline`, `Timeline`, and `HierarchyTree`) without custom implementations.

# 3. Cross-Module Dependencies
- **Core Module:** Modifies/extends the kernel tenant context logic.
- **Finance Module:** Highly dependent on the `base_currency` defined here for all monetary transactions.
- **All Modules (Global):** Any table requiring data scoping relies on the `subsidiary_id` established by this feature.

# 4. Implementation Sequence
- **Phase 1 (Database):** Create the `settings_entities` SQLAlchemy model (or update `core` schema) inheriting from `BESBase` with self-referential `parent_id` foreign keys. Generate Alembic migrations.
- **Phase 2 (APIs):** Implement FastAPI router for entities with hierarchical GET endpoints, POST/PUT actions incorporating strict cycle detection logic, and DELETE endpoints with soft-delete validations.
- **Phase 3 (Frontend Setup):** Initialize the `@bes/settings` Nx library (if not already present), wire up API client hooks.
- **Phase 4 (UI - Views):** Build the `Company Structure` dashboard integrating the `@bes/shared-ui` `HierarchyTree`.
- **Phase 5 (UI - Interactions):** Implement the `Entity Drawer` utilizing `Tabs`, `Form`, `ProcessPipeline`, and `Timeline` for audit history.
