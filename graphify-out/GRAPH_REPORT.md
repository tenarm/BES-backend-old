# Graph Report - bes-backend  (2026-05-22)

## Corpus Check
- 74 files · ~17,121 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 979 nodes · 1177 edges · 97 communities (82 shown, 15 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 116 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `949c4319`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]

## God Nodes (most connected - your core abstractions)
1. `finance` - 19 edges
2. `BESBase` - 17 edges
3. `NotificationRule` - 16 edges
4. `hr` - 15 edges
5. `Notification` - 15 edges
6. `sales` - 13 edges
7. `inventory` - 13 edges
8. `manufacturing` - 13 edges
9. `require_licensed_feature()` - 13 edges
10. `sales` - 13 edges

## Surprising Connections (you probably didn't know these)
- `seed_data()` --calls--> `Vendor`  [INFERRED]
  scratch/seed_ap.py → core/core/models.py
- `lifespan()` --calls--> `get_engine()`  [INFERRED]
  boiler-plate-instance/app_template/lifespan.py → core/core/database.py
- `create_entity_endpoint()` --calls--> `success_response()`  [INFERRED]
  extensions/settings/settings/router.py → core/core/responses.py
- `create_entity_endpoint()` --calls--> `success_response()`  [INFERRED]
  extensions/sales/sales/router.py → core/core/responses.py
- `create_entity_endpoint()` --calls--> `success_response()`  [INFERRED]
  extensions/finance/finance/router.py → core/core/responses.py

## Communities (97 total, 15 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (39): bootstrap(), health(), Returns the client configuration and the authenticated user's permissions,     f, _bootstrap_config(), Reads the client onboarding config, resolves paths, and injects environment, BaseHTTPMiddleware, get_async_session(), _get_default_engine() (+31 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (49): delete, read, write, delete, read, write, delete, read (+41 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (49): delete, read, write, delete, read, write, delete, read (+41 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (49): delete, read, write, delete, read, write, manufacturing, bom (+41 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (49): delete, read, write, delete, read, write, delete, read (+41 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (26): is_feature_licensed(), LicensingError, Checks if a specific sub-feature is licensed based on the active client schema., Asserts that a sub-feature is licensed.          If the check fails, raises:, Bespoke exception raised when a client attempts to access a feature outside thei, require_licensed_feature(), paginated_response(), Wraps data with pagination metadata in the standard envelope. (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (41): delete, read, write, delete, read, write, delete, read (+33 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (41): delete, read, write, delete, read, write, delete, read (+33 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (41): delete, read, write, delete, read, write, delete, read (+33 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (12): ABC, ExtensionManifest, Returns a dict of {event_type: handler_function} to register         with the ev, Optional hook called during application startup., Optional hook called during application shutdown., Formal contract for BES extension modules.          Every extension MUST impleme, AbstractFileStorage, System-wide abstract file storage service to ensure Day 2 readiness     for S3/G (+4 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (34): bi, cross_module_aggregation, custom_report_builder, dashboard_builder, data_export, drill_down_reports, report_access, scheduled_reports (+26 more)

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (33): delete, read, write, delete, read, write, delete, read (+25 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (33): delete, read, write, delete, read, write, delete, read (+25 more)

### Community 13 - "Community 13"
Cohesion: 0.06
Nodes (33): delete, read, write, delete, read, write, delete, read (+25 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (16): _AuditBroadcaster, AuditLog, EventStore, FieldChangeLog, ImmutableBase, log_action(), BES Audit & Traceability System.  Provides immutable, tamper-proof audit logging, Detailed before/after snapshot of individual field mutations.     Linked to Audi (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (26): error_response(), Registers global exception handlers on the FastAPI application     to ensure all, setup_exception_handlers(), StandardResponse, success_response(), audit_sse_stream(), create_rule(), delete_rule() (+18 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (22): create_access_token(), create_refresh_token(), decode_token(), get_current_user(), _get_secret_key(), Creates a refresh token and returns (token_string, expiry_datetime)., Decodes and validates a JWT token. Raises on failure., FastAPI dependency that validates the JWT and returns the active User.      Eage (+14 more)

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (22): BESBase, BESBase, Customer, Product, Unified base model for all BES tables.     Provides UUID primary keys, audit tra, Role-based access control: each role defines a permission set     stored as a ne, Stores issued refresh tokens for revocation support.     Each row represents one, RefreshToken (+14 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (18): display_name, modules, crm, document_management, finance, hr, inventory, sales (+10 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (18): ActionDefinition, Config, _find_project_root(), get_active_licensed_modules(), _load_process_definitions(), ProcessDefinition, ProcessStep, Tries to find the active client's LICENSED_MODULES from loaded sys.modules. (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (14): 1. Requirements, 2. Installation, 3. Running an Instance, 4. API Documentation, Adding a New Extension, 🏗️ Architecture, BES Factory Backend, code:bash (pdm install) (+6 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (6): BaseModel, BaseEventPayload, Standard envelope for all inter-module events.     Ensures type safety, correlat, emit_entity_created(), emit_entity_created(), emit_entity_created()

### Community 22 - "Community 22"
Cohesion: 0.22
Nodes (9): lifespan(), get_password_hash(), cleanup_expired_tokens(), Seeds default roles if they don't exist., Seeds an admin user if none exists.     Password is sourced from INITIAL_ADMIN_P, Fix #14: Purges revoked and expired RefreshToken rows.      RefreshToken rows ac, seed_admin_user(), seed_roles() (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.2
Nodes (9): client_id, client_name, custom_config, database_url, licensed_modules, plan, registered_at, status (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.29
Nodes (5): AuditService, Central service for recording audit trail entries.     Every mutation in the BES, PaginationParams, Reusable FastAPI dependency for pagination.      MAX_PAGE_SIZE is read from the, NotificationRuleCreate

### Community 25 - "Community 25"
Cohesion: 0.6
Nodes (5): main(), to_camel_case(), update_admin_permissions_json(), update_packages_json(), update_root_pyproject()

### Community 26 - "Community 26"
Cohesion: 0.4
Nodes (5): delete, read, write, finance, bank_cash

### Community 27 - "Community 27"
Cohesion: 0.4
Nodes (5): hr, performance_appraisal, delete, read, write

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (4): delete, read, write, ar

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (4): delete, read, write, budgeting

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (4): delete, read, write, ap

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (4): delete, read, write, audit_trail

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (4): delete, read, write, coa

### Community 33 - "Community 33"
Cohesion: 0.5
Nodes (4): delete, read, write, cost_center

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (4): intercompany, delete, read, write

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (4): mis_reporting, delete, read, write

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (4): payroll_integration, delete, read, write

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (4): period_end_close, delete, read, write

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (4): project_cost_accounting, delete, read, write

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (4): purchase_invoices, delete, read, write

### Community 40 - "Community 40"
Cohesion: 0.5
Nodes (4): tax, delete, read, write

### Community 41 - "Community 41"
Cohesion: 0.5
Nodes (4): fixed_asset, delete, read, write

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (4): gl, delete, read, write

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (4): multi_currency, delete, read, write

### Community 44 - "Community 44"
Cohesion: 0.5
Nodes (4): vendors, delete, read, write

### Community 45 - "Community 45"
Cohesion: 0.5
Nodes (4): delete, read, write, hr_analytics

### Community 46 - "Community 46"
Cohesion: 0.5
Nodes (4): delete, read, write, attendance

### Community 47 - "Community 47"
Cohesion: 0.5
Nodes (4): delete, read, write, employee_master

### Community 48 - "Community 48"
Cohesion: 0.5
Nodes (4): delete, read, write, ess_portal

### Community 49 - "Community 49"
Cohesion: 0.5
Nodes (4): leave_management, delete, read, write

### Community 50 - "Community 50"
Cohesion: 0.5
Nodes (4): loan_advance, delete, read, write

### Community 51 - "Community 51"
Cohesion: 0.5
Nodes (4): org_structure, delete, read, write

### Community 52 - "Community 52"
Cohesion: 0.5
Nodes (4): payroll_processing, delete, read, write

### Community 53 - "Community 53"
Cohesion: 0.5
Nodes (4): statutory_compliance, delete, read, write

### Community 54 - "Community 54"
Cohesion: 0.5
Nodes (4): recruitment, delete, read, write

### Community 55 - "Community 55"
Cohesion: 0.5
Nodes (4): separation_fnf, delete, read, write

### Community 56 - "Community 56"
Cohesion: 0.5
Nodes (4): shift_roster, delete, read, write

### Community 57 - "Community 57"
Cohesion: 0.5
Nodes (4): training_development, delete, read, write

### Community 58 - "Community 58"
Cohesion: 0.67
Nodes (3): Automatically set updated_at to current UTC time before any update., receive_before_update(), utc_now()

## Knowledge Gaps
- **454 isolated node(s):** `read`, `write`, `delete`, `read`, `write` (+449 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `finance` connect `Community 26` to `Community 32`, `Community 33`, `Community 34`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 39`, `Community 40`, `Community 41`, `Community 10`, `Community 42`, `Community 43`, `Community 44`, `Community 28`, `Community 29`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `hr` connect `Community 27` to `Community 10`, `Community 45`, `Community 46`, `Community 47`, `Community 48`, `Community 49`, `Community 50`, `Community 51`, `Community 52`, `Community 53`, `Community 54`, `Community 55`, `Community 56`, `Community 57`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `sales` connect `Community 4` to `Community 10`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `BESBase` (e.g. with `NotificationRule` and `Notification`) actually correct?**
  _`BESBase` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `str` (e.g. with `_bootstrap_config()` and `bootstrap()`) actually correct?**
  _`str` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `NotificationRule` (e.g. with `BESBase` and `Role`) actually correct?**
  _`NotificationRule` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Reads the client onboarding config, resolves paths, and injects environment`, `Returns the client configuration and the authenticated user's permissions,     f`, `Creates a refresh token and returns (token_string, expiry_datetime).` to the rest of the system?**
  _539 weakly-connected nodes found - possible documentation gaps or missing edges._