## 1. Module & Feature Name
- **Module**: Settings
- **Feature Name**: System Audit Log & Activity Trail

## 2. Information Architecture
- **Main Page (`/settings/audit-log`)**: A comprehensive "Audit Explorer" view centered around a high-density Data Table.
- **Top Bar / Filters**: Advanced search and filtering controls (Date Range Picker, Module Select, Action Type Select, User Select, Subsidiary Select).
- **Drawer (`Audit Event Details`)**: Opens from the right when an administrator clicks on a specific audit log entry.
  - **Header**: Event Title (e.g., "Updated Sales Order #SO-102") and Status/Severity Badge.
  - **Tab 1: Summary**: Read-only overview of the event context (Timestamp, Actor Name, IP Address, Device/Browser context, Module, Action Type).
  - **Tab 2: Field Mutations**: A side-by-side or tabular diff view showing the exact before-and-after values for any modified fields.
  - **Tab 3: Data Lineage (Correlation)**: A visual representation of the business workflow this event belongs to (e.g., showing the connected PR &rarr; PO &rarr; GRN &rarr; Invoice chain).
  - **Tab 4: Entity Timeline**: A reverse-chronological feed of *all* other audit events related to this specific record/entity.

## 3. Process Chain & Workflow
- **Macro View (`ProcessPipeline`)**: Utilized within the **Data Lineage** tab of the Drawer to visually map out the transaction's lifecycle across modules using the correlation IDs (e.g., showing that this `Purchase Invoice` event is part of a larger `PR -> PO -> GRN -> Invoice` pipeline).
- **Micro View (`Timeline`)**: Utilized within the **Entity Timeline** tab of the Drawer to show the chronological history of the specific record being inspected (e.g., "Created by User A" &rarr; "Updated by User B" &rarr; "Approved by User C").

## 4. Shared UI Components
The following `@bes/shared-ui` components will be utilized:
- `DataTable`: For the main master ledger of audit events (requires server-side pagination due to data volume).
- `Drawer`: For inspecting the granular details of a single audit event.
- `ProcessPipeline`: For visualizing cross-module data lineage and correlation.
- `Timeline`: For displaying the chronological history of a specific entity.
- `DatePicker` / `Select` / `TextField`: For the advanced filtering bar.
- `Badge`: For event severity (e.g., Info, Warning, Critical Security Event) and action types (Create, Update, Delete).
- `Skeleton`: For loading states during heavy database queries.
- `Button` (with Icon): For the "Export Report" actions (CSV/PDF).

## 5. UI States & Walkthrough

**Empty State**
- Should rarely be empty in a live system, but if filtered to yield no results, the `DataTable` will display an empty state illustration: "No audit records match your filters."

**Loading State**
- Fetching millions of log rows can take time; the main view will use a `Skeleton` table.
- Drawer tabs will use `Skeleton` blocks while fetching granular `FieldChangeLog` data or correlation chains.

**Error Boundaries**
- Graceful error states if a correlation chain breaks or if a referenced entity has been hard-deleted (though standard BES practice is soft-delete).

**Data Table Columns (Main View)**
1. **Timestamp** (e.g., `2024-05-17 14:30:00`)
2. **Actor / User** (e.g., `Admin User`)
3. **Module** (e.g., `Sales`)
4. **Action** (e.g., `UPDATE`) - Rendered as a `Badge`.
5. **Entity Type** (e.g., `SalesOrder`)
6. **Entity ID / Ref** (e.g., `SO-2024-001`)
7. **Severity / Type** (e.g., `Business`, `Security`) - Rendered as a `Badge`.
8. **Actions** (View Details icon)

**Drawer Walkthrough**
- Admin clicks on a "Security Event: Failed Login" row.
  - The Drawer opens. The **Summary Tab** displays the IP address and failure reason. The **Mutations Tab** is hidden (no data changed).
- Admin clicks on an "UPDATE" event for a Sales Order.
  - The Drawer opens. The **Mutations Tab** displays a dedicated diff table:
    - *Column 1*: Field Name (e.g., `total_amount`)
    - *Column 2*: Old Value (e.g., `$1,000.00`)
    - *Column 3*: New Value (e.g., `$1,200.00`)
  - The Admin clicks the **Data Lineage Tab** to see the `ProcessPipeline` showing the Quote &rarr; Sales Order &rarr; Invoice progression.
  - The Admin clicks the **Entity Timeline Tab** to see all previous edits made to this specific Sales Order since its creation.
