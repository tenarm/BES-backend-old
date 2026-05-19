## 1. Module & Feature Name
- **Module**: Settings
- **Feature Name**: Number Series / Sequence Management

## 2. Information Architecture
- **Main Page (`/settings/number-series`)**: The primary view featuring a Data Table listing all configured Number Series rules.
- **Top Bar**: Search bar, Filter by Document Type/Subsidiary/Status, and a primary "Create Series" action button.
- **Drawer (`Number Series Details`)**: Opens from the right when creating a new series or clicking on an existing one.
  - **Header**: Sequence Name (e.g., "Sales Invoices - US Subsidiary") and Status Badge.
  - **Tab 1: Configuration**: Form for Prefix, Suffix, Padding, Start Number, Reset Frequency, and dynamic preview.
  - **Tab 2: Assignments**: UI to link this sequence to specific Document Types and Subsidiaries (`subsidiary_id`).
  - **Tab 3: Maintenance**: Tools for manual counter adjustment (restricted access).
  - **Tab 4: History**: Vertical Timeline of audit events (changes to config, assignments, manual counter updates, automated resets).

## 3. Process Chain & Workflow
- **Macro View (`ProcessPipeline`)**: Visible at the top of the Drawer to indicate the lifecycle of a Number Series.
  - `Draft` (Configuring) &rarr; `Active` (In Use) &rarr; `Inactive` (Archived/Deactivated)
- **Micro View (`Timeline`)**: Located in the "History" tab of the Drawer, tracking audit events:
  - "User [Name] created sequence rule."
  - "User [Name] assigned sequence to Sales Invoice for Subsidiary A."
  - "System triggered annual reset."
  - "User [Name] manually adjusted current number from 150 to 200."

## 4. Shared UI Components
The following `@bes/shared-ui` components will be utilized. No custom components are required.
- `DataTable`: For the main list of Number Series.
- `Drawer`: For the detailed side panel for creating/editing a series.
- `ProcessPipeline`: For the macro state tracker at the top of the Drawer.
- `Timeline`: For the audit history in the Drawer.
- `FormLayout`, `TextField`, `Select`, `Switch`: For configuration inputs.
- `Badge`: For status indicators (`Active`, `Inactive`, `Draft`).
- `Skeleton`: For loading states in the table and drawer.
- `Alert` / `Dialog`: For warnings when an admin attempts to manually adjust a sequence counter.

## 5. UI States & Walkthrough

**Empty State**
- The main table displays an empty state illustration with a message "No Number Series Configured" and a primary Call-to-Action "Create First Number Series".

**Loading State**
- A `Skeleton` table structure replaces the data grid while fetching the list of series.
- When opening the Drawer, `Skeleton` blocks represent the form fields and tabs until the detailed configuration is fetched.

**Error Boundaries**
- A standard toast/notification will catch and display API errors (e.g., "Failed to save sequence", "Duplicate sequence assignment detected for Subsidiary A").
- Form validation errors will display inline below the respective inputs.

**Data Table Columns (Main View)**
1. **Sequence Name** (e.g., `Sales Invoice - US`)
2. **Document Type** (e.g., `Invoice`)
3. **Subsidiary** (e.g., `US Subsidiary` or `Global`)
4. **Format Preview** (e.g., `INV-{YYYY}-00001`)
5. **Current Number** (e.g., `124`)
6. **Reset Frequency** (e.g., `Annually`)
7. **Status** (`Active`, `Inactive`)
8. **Actions** (Context menu to Edit, Deactivate, or view Audit History)

**Drawer Walkthrough**
- **Configuration Tab**:
  - Contains inputs for **Prefix**, **Suffix** (with helper text explaining variables like `{YYYY}`, `{MM}`, `{SUB_CODE}`).
  - **Padding Length** (numeric input) and **Start Number**.
  - **Reset Frequency** dropdown (`Never`, `Monthly`, `Annually`).
  - **Dynamic Preview Box**: A visually distinct read-only box that updates in real-time as the user types (e.g., displaying "Preview: INV-2024-00001").
- **Assignments Tab**:
  - Allows selecting the Target Entity/Document Type from a searchable `Select`.
  - Allows selecting the applicable `subsidiary_id` (or 'All' for global fallback).
- **Maintenance Tab (Restricted)**:
  - Displays the current counter.
  - An editable `TextField` allows highly privileged users to jump the sequence forward.
  - Requires a confirmation `Dialog` explaining that skipping numbers will create gaps in the sequence, followed by an immediate audit log entry.
