# 1. Module & Feature Name
**Module:** Settings
**Feature:** User Management & RBAC

# 2. Core Purpose
Provides centralized identity management and granular, context-aware access control across the BES platform. It ensures that employees can only access authorized modules, perform permitted actions, and interact with data strictly within their allowed corporate subsidiaries.

# 3. Functionality Groups
- User Administration
- Role & Permission Management
- Subsidiary Context Mapping
- Audit & Security Review

# 4. Detailed Functionalities List

*User Administration*
- **Create User:** Provision a new identity in the system with basic details (Name, Email).
- **Update User Profile:** Modify basic user information.
- **Suspend/Deactivate User:** Revoke system access by soft-deleting or marking the user as inactive.
- **View User Directory:** Display a paginated list of all users, showing their status, primary roles, and default subsidiary.
- **Force Session Revocation:** Terminate all active sessions (refresh tokens) for a specific user to force immediate re-authentication.

*Role & Permission Management*
- **Create Role:** Define a new role by selecting a combination of granular permissions across available licensed modules (e.g., `finance:coa:write`, `sales:invoice:read`).
- **Edit Role Permissions:** Modify the permission sets of existing custom roles.
- **Deactivate Role:** Soft delete an unused role (restricted for system-provided default roles like Super Admin).
- **View Roles Matrix:** Display a grid summarizing available roles and their assigned access levels.

*Subsidiary Context Mapping*
- **Assign Roles to User:** Link one or more functional roles to a user identity.
- **Scope User Access by Subsidiary:** Restrict a user's operational context by mapping them to specific `subsidiary_id`s (e.g., restricting a clerk to only the "EU Subsidiary").
- **Set Default Subsidiary:** Define the primary operational context a user logs into by default.

*Audit & Security Review*
- **View User Activity Timeline:** Display an audit feed of permission changes, role assignments, and login history for a specific user.
- **Review Role Assignments:** Quickly visualize which active users currently hold a specific role to ensure compliance and prevent privilege creep.
