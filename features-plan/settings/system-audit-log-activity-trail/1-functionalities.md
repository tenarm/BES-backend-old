# 1. Module & Feature Name
**Module:** Settings
**Feature:** System Audit Log & Activity Trail

# 2. Core Purpose
Provides a centralized, immutable, and tamper-proof ledger of every system mutation and user action across all BES modules. Built on top of the `core` Audit engine (`AuditLog` and `FieldChangeLog`), this feature ensures regulatory compliance, tracks precise field-level data changes, and allows administrators to trace user activities, security events, and multi-step data lineage.

# 3. Functionality Groups
- Central Audit Dashboard
- Entity & Field-Level Timelines
- Process Correlation & Data Lineage
- Compliance & Export

# 4. Detailed Functionalities List

*Central Audit Dashboard*
- **View Global Activity Feed:** Display a master ledger of all `AuditLog` events across the system, showing the actor, timestamp, module, and action performed.
- **Advanced Filtering & Search:** Filter the massive log dataset by `user_id`, `module`, `action_type`, `subsidiary_id`, or specific date ranges.

*Entity & Field-Level Timelines*
- **View Entity Timeline (`get_entity_timeline`):** Track the complete lifecycle history of any specific record (e.g., a Sales Order, an Employee Profile) in a chronological feed.
- **Review Field Mutations (`FieldChangeLog`):** Inspect precise before-and-after data snapshots for any update action, identifying exactly which fields were altered.

*Process Correlation & Data Lineage*
- **Trace Business Workflows (`get_correlation_chain`):** Follow a transaction through its entire lifecycle across modules (e.g., tracing a Purchase Requisition through PO, GRN, and AP Invoice) using correlation IDs.

*Compliance & Export*
- **Monitor Security Events:** Track failed login attempts, unauthorized access errors, and permission escalation events.
- **Export Audit Reports:** Securely extract filtered subsets of the audit log to immutable formats (CSV/PDF) for external regulatory audits (e.g., SOC2, HIPAA, GDPR).
