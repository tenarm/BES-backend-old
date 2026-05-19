# 1. Feature & Scope
**Feature:** User Management & RBAC
**Scope:** Providing the administrative interfaces and API logic to manage `core_users`, `core_roles`, and their subsidiary-specific access mappings. Ensures that all context-aware authorization (`<module>:<resource>:<action>`) across the platform is properly governable via the UI.

# 2. Architectural Compliance Sign-off
- [x] **Hub-and-Spoke MDM:** Correctly identifies that `User` and `Role` models must reside in the `core` schema, while the `settings` module provides the administrative spoke.
- [x] **BESBase Heritage:** Tables inherit from `BESBase` including the junction table to ensure complete audit trails (`created_by`).
- [x] **Context-Aware RBAC:** Fully defines the required structure (Module:Resource:Action) and ties it directly to the user's `subsidiary_id` scope.
- [x] **Soft Deletes:** Suspension mechanisms correctly utilize `is_deleted=True` to preserve historical audit logs.
- [x] **Shared UI:** Leverages `ProcessPipeline`, `Timeline`, and standard data tables.

# 3. Cross-Module Dependencies
- **Core Kernel:** The `core_users` table is the source of truth for the kernel authentication middleware and the `created_by` column on every `BESBase` table globally. Changes here directly impact active sessions.

# 4. Implementation Sequence
- **Phase 1 (Database):** Create/Verify `core_users`, `core_roles`, and `core_user_roles` models inheriting from `BESBase`. Ensure JSONB fields are utilized for permissions arrays.
- **Phase 2 (APIs):** Build FastAPI router in the `settings` module to perform CRUD on the `core` auth models. Implement role assignment endpoint ensuring `subsidiary_id` boundaries are validated.
- **Phase 3 (Frontend Setup):** Create state bindings (Zustand/React Query) in the `@bes/settings` library to interface with the auth endpoints.
- **Phase 4 (UI - Views):** Construct the `Security & Access` page with top-level tabs for Users and Roles, featuring paginated data tables.
- **Phase 5 (UI - Interactions):** Build the User Drawer and Role Drawer utilizing `TransferList` for assigning permissions, along with the `ProcessPipeline` and `Timeline` for audit visibility.
