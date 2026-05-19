# 1. Module & Feature Name
**Module:** Settings
**Feature:** User Management & RBAC

# 2. Database Schema (YAML)
```yaml
tables:
  core_users:
    description: "System users. Resides in `core` schema as it's required by BESBase `created_by`."
    inherits: "BESBase (id, created_at, updated_at, created_by, is_deleted, subsidiary_id, metadata_)"
    columns:
      email:
        type: String
        unique: true
        nullable: false
      full_name:
        type: String
        nullable: false
      status:
        type: String
        nullable: false
        description: "Lifecycle status: 'Invited', 'Active', 'Suspended'."
      default_subsidiary_id:
        type: UUID
        nullable: true
        description: "The primary organizational context the user logs into."

  core_roles:
    description: "System and custom roles. Resides in `core` schema."
    inherits: "BESBase"
    columns:
      name:
        type: String
        nullable: false
      description:
        type: String
        nullable: true
      permissions:
        type: JSONB
        nullable: false
        description: "List of permission strings e.g. ['finance:coa:read', 'settings:users:write']."
      status:
        type: String
        nullable: false
        description: "Lifecycle status: 'Draft', 'Active'."

  core_user_roles:
    description: "Junction table mapping users to roles within a specific subsidiary context."
    inherits: "BESBase"
    columns:
      user_id:
        type: UUID
        nullable: false
      role_id:
        type: UUID
        nullable: false
      context_subsidiary_id:
        type: UUID
        nullable: true
        description: "The specific subsidiary where this role applies. If null, role applies globally."
    foreign_keys:
      - column: user_id
        references: core_users.id
      - column: role_id
        references: core_roles.id
```

# 3. Hub-and-Spoke MDM Mapping
- **Core Residency:** `User` and `Role` models reside natively in the central `core` schema. This is mandatory because every table in the system (via `BESBase`) relies on `core_users.id` for the `created_by` audit column, and the kernel's authentication middleware requires these models before any module is loaded.
- The `settings` module acts as the administrative "spoke" providing the interfaces, workflow pipelines, and APIs to manage these central `core` records.

# 4. REST APIs
```yaml
endpoints:
  - method: GET
    path: /api/v1/settings/users
    description: Fetch paginated users directory.
    response: { "status": "success", "data": [...], "metadata": {"count": 10}, "error": null }
    
  - method: POST
    path: /api/v1/settings/users
    description: Provision a new user.
    payload: { "email": "...", "full_name": "...", "status": "Invited" }
    
  - method: PUT
    path: /api/v1/settings/users/{id}
    description: Update basic user info or status.
    
  - method: POST
    path: /api/v1/settings/users/{id}/roles
    description: Assign roles to a user with subsidiary context.
    payload: { "role_ids": ["..."], "context_subsidiary_ids": ["..."] }
    
  - method: GET
    path: /api/v1/settings/roles
    description: Fetch all system and custom roles.
    
  - method: POST
    path: /api/v1/settings/roles
    description: Create a custom role.
    payload: { "name": "...", "permissions": ["finance:coa:write"] }
```

# 5. Pub/Sub Events
- `SETTINGS_USER_PROVISIONED`: Emitted when a new user is created.
- `SETTINGS_USER_SUSPENDED`: Emitted to immediately revoke access system-wide.
- `SETTINGS_ROLE_UPDATED`: Emitted when permissions change, triggering active session token invalidation for affected users.

# 6. RBAC Permissions
- `settings:users:read`: View user directory.
- `settings:users:write`: Create, edit, or suspend users; assign roles.
- `settings:roles:read`: View available roles.
- `settings:roles:write`: Create or modify custom roles and their permission sets.
