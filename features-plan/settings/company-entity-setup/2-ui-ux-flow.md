# 1. Module & Feature Name
**Module:** Settings
**Feature:** Company / Entity Setup

# 2. Information Architecture
- **Settings Dashboard:** Entry point via Shell Sidebar.
  - **Company Structure Page:** Main view containing an interactive tree of the corporate hierarchy.
    - **Entity Drawer (Right Panel):** Opens when clicking "Add Entity" or editing an existing entity.
      - **Tab 1: General Info:** Legal name, type (root/subsidiary/branch).
      - **Tab 2: Localization:** Base currency, timezone, addresses.
      - **Tab 3: Registration:** Tax IDs, EIN, VAT.
      - **Tab 4: History:** Timeline of changes to this entity.

# 3. Process Chain & Workflow
- **Macro View (`ProcessPipeline`):** 
  - Located at the top of the Entity Drawer.
  - Stages: `Draft` → `Active` → `Suspended`.
- **Micro View (`Timeline`):** 
  - Located in the "History" tab of the drawer.
  - Logs events like "Entity created", "Base currency changed to EUR", "Moved under Acme Corp EU".

# 4. Shared UI Components
- `PageHeader`: Title and global actions (e.g., "Create Root Entity").
- `HierarchyTree`: Interactive tree visualization of parent/child relationships.
- `Drawer`: Right panel for creating/editing entities without leaving context.
- `Tabs`: Inside the drawer to split forms into General, Localization, Registration, and History.
- `Form`, `Input`, `Select`, `Switch`: For form controls within the drawer.
- `ProcessPipeline`: At the top of the drawer to show lifecycle status.
- `Timeline`: For the audit history in the drawer.
- `SkeletonTree` / `SkeletonCard`: For loading states.
- `EmptyState`: Shown when no root entity exists.

# 5. UI States & Walkthrough

*Empty State:*
- **Condition:** No root entity exists in the system.
- **UI:** A centered `EmptyState` component with a large "Initialize Root Company" primary button. No hierarchy tree is visible.

*Walkthrough: Adding a Subsidiary:*
1. **Initial Load:** User opens the "Company Structure" page. The `HierarchyTree` loads (showing `SkeletonTree` while fetching).
2. **Action:** User clicks the "Add Child" icon on the Root Entity node.
3. **Drawer Opens:** The `Drawer` slides in from the right. The `ProcessPipeline` shows "Draft" status.
4. **Form Entry:** User fills out the "General Info" tab, then clicks "Next" or selects the "Localization" tab to select the `base_currency` and `timezone` using `Select` components.
5. **Submission:** User clicks "Save". The Drawer switches to a disabled/loading state (spinner on button).
6. **Success:** A toast notification appears. The `Drawer` closes, and the new entity animates into the `HierarchyTree`. 
7. **Timeline Log:** The `Timeline` component (in the History tab) updates with a "Subsidiary created" entry.

*Error Boundaries & Licensing:*
- If `settings` is `READONLY_EXTENSIONS`, the "Add Child" buttons and Form save buttons are hidden or disabled. The `ProcessPipeline` is visible but non-interactive.
- If a cycle is detected during re-parenting, an inline error banner displays above the form.
