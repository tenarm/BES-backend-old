# 1. Module & Feature Name
**Module:** Settings
**Feature:** User Management & RBAC

# 2. Information Architecture
- **Settings Dashboard:** Entry point via Shell Sidebar.
  - **Security & Access Page:** Main view with two primary sub-tabs:
    - **Sub-tab 1: Users:** Data table of all users.
      - **User Drawer (Right Panel):** Opens when creating or editing a user.
        - **Tab 1: Profile:** Basic details, status.
        - **Tab 2: Roles & Context:** Role assignment (`TransferList`), Allowed Subsidiaries.
        - **Tab 3: Audit Log:** Login history and permission changes.
    - **Sub-tab 2: Roles:** Matrix/Table of available custom and system roles.
      - **Role Drawer (Right Panel):** Opens when creating/editing a role.
        - **Tab 1: Role Details:** Name, description.
        - **Tab 2: Permissions:** Granular checklist or tree (`finance:coa:write`, etc.).

# 3. Process Chain & Workflow
- **Macro View (`ProcessPipeline`):**
  - **For Users:** Located at the top of the User Drawer. Stages: `Invited` → `Active` → `Suspended`.
  - **For Roles:** Located at the top of the Role Drawer. Stages: `Draft` → `Active`.
- **Micro View (`Timeline`):**
  - Located in the "Audit Log" tab of the User Drawer (e.g., "Role 'Finance Clerk' granted by Admin", "Session revoked").

# 4. Shared UI Components
- `PageHeader` & `Tabs` (Page level): To toggle between Users and Roles.
- `Table` (with pagination/sorting): For listing Users and Roles.
- `Drawer`: Right panel for creating/editing users and roles.
- `Tabs` (Drawer level): To organize complex user and role configurations.
- `TransferList` / `CheckboxGroup`: To assign roles to a user or permissions to a role.
- `Select` (Multi-select): For mapping a user to multiple `subsidiary_id` contexts.
- `Badge`: For displaying status (Active/Suspended) inside the table.
- `ProcessPipeline`: At the top of the drawers.
- `Timeline`: For the user audit log.
- `SkeletonTable`: For loading states.

# 5. UI States & Walkthrough

*Walkthrough: Creating a User & Assigning Roles:*
1. **Initial Load:** User navigates to Settings > Security & Access. The `Table` of users loads (displaying a `SkeletonTable` initially).
2. **Action:** Admin clicks "Add User".
3. **Drawer Opens:** The `Drawer` slides in from the right. The `ProcessPipeline` displays "Invited".
4. **Profile Tab:** Admin enters Name and Email in the `Form`.
5. **Roles & Context Tab:** Admin selects the "Roles & Context" tab. They use a `TransferList` to move the "Finance Clerk" role from 'Available' to 'Assigned'. They use a multi-select `Select` component to define the allowed `subsidiary_id`s.
6. **Submission:** Admin clicks "Save". A loading state appears on the button.
7. **Success:** The drawer closes, the `Table` refreshes, and the new user appears with an "Active" `Badge`.
8. **Timeline Log:** The `Timeline` component in that user's drawer logs "User provisioned" and "Roles assigned".

*Error Boundaries & Licensing:*
- **READONLY Mode:** If the module is in `READONLY_EXTENSIONS`, the "Add User" and "Add Role" buttons are hidden. The `TransferList` components are rendered in read-only mode.
- **Privilege Error:** If an admin tries to assign a role they do not have authority over, a form validation error banner is displayed.
- **Empty State:** If the role search yields no results, a standard `EmptyState` component is shown in the Table.
