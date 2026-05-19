# 1. Module & Feature Name
**Module:** Settings
**Feature:** Company / Entity Setup

# 2. Database Schema (YAML)
```yaml
tables:
  settings_entities:
    description: "Stores the corporate hierarchy (root, subsidiary, branch). May alternatively reside in `core` depending on MDM standards."
    inherits: "BESBase (id, created_at, updated_at, created_by, is_deleted, subsidiary_id, metadata_)"
    columns:
      parent_id:
        type: UUID
        nullable: true
        description: "Self-referencing foreign key. Null for the Root Company."
      name:
        type: String
        nullable: false
        description: "Display name (e.g., 'Acme Corp EU')"
      legal_name:
        type: String
        nullable: true
        description: "Official legal name for reporting."
      type:
        type: String
        nullable: false
        description: "Enum: 'root', 'subsidiary', or 'branch'."
      registration_number:
        type: String
        nullable: true
      tax_id:
        type: String
        nullable: true
      base_currency:
        type: String
        nullable: false
        description: "Default currency code (e.g., 'USD', 'EUR'). Drives the Money Rule."
      timezone:
        type: String
        nullable: true
      status:
        type: String
        nullable: false
        description: "Lifecycle status: 'Draft', 'Active', 'Suspended'."
    foreign_keys:
      - column: parent_id
        references: settings_entities.id
```

# 3. Hub-and-Spoke MDM Mapping
- **Core Kernel Foundation:** This feature manages the ultimate source of truth for the tenant isolation mechanism.
- Every `BESBase` inherited table across the system requires a `subsidiary_id`. That column intrinsically maps to `settings_entities.id`. 
- Even if the table resides in the `settings` schema, it acts as a central MDM hub for the entire platform's multi-tenant architecture.

# 4. REST APIs
```yaml
endpoints:
  - method: GET
    path: /api/v1/settings/entities
    description: Fetch hierarchical list of entities.
    response: |
      { 
        "status": "success", 
        "data": [{ "id": "...", "name": "...", "children": [...] }], 
        "metadata": { "count": 1, "page": 1 }, 
        "error": null 
      }
      
  - method: POST
    path: /api/v1/settings/entities
    description: Create a new entity (Root or Child).
    payload: |
      { 
        "parent_id": "uuid|null", 
        "name": "...", 
        "type": "subsidiary", 
        "base_currency": "USD" 
      }
      
  - method: PUT
    path: /api/v1/settings/entities/{id}
    description: Update entity details or re-parent (cycle detection enforced).
    
  - method: DELETE
    path: /api/v1/settings/entities/{id}
    description: Soft delete an entity (sets is_deleted=True, status='Suspended').
```

# 5. Pub/Sub Events
- `SETTINGS_ENTITY_CREATED`: Emitted when a new subsidiary/branch is initialized.
- `SETTINGS_ENTITY_UPDATED`: Emitted on changes to `base_currency` or hierarchy.
- `SETTINGS_ENTITY_SUSPENDED`: Emitted on soft-delete to alert other modules to block transactions for this context.

# 6. RBAC Permissions
- `settings:entities:read`: Required to view the corporate hierarchy.
- `settings:entities:write`: Required to create, update, or restructure the corporate entities.
