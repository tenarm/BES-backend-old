## 1. Module & Feature Name
- **Module**: Settings
- **Feature Name**: Number Series / Sequence Management

## 2. Core Purpose
The Core Purpose of Number Series Management is to provide a centralized, thread-safe, and configurable mechanism to auto-generate unique, sequential, and formatted alphanumeric identifiers for various transactions and master data records across the BES system (e.g., Invoices, Purchase Orders, Items, Customers). It ensures consistency, auditability, and compliance with organizational and legal numbering formats, supporting multi-tenant scoping and dynamic formatting such as prefixing with financial years or subsidiary codes.

## 3. Functionality Groups
1. **Sequence Configuration & Setup**: Creating and defining the rules and formats for number series.
2. **Sequence Assignment**: Mapping specific sequences to particular document types, subsidiaries, or modules.
3. **Sequence Execution & Generation**: Generating the next number atomically when a document is created.
4. **Sequence Maintenance & Audit**: Handling periodic resets, sequence corrections, and tracking changes.

## 4. Detailed Functionalities List

**Group 1: Sequence Configuration & Setup**
- **Create Sequence Rule**: Define a new number sequence, specifying its name, description, prefix, suffix, and starting number.
- **Configure Padding / Length**: Set the fixed length of the numeric part of the sequence and define the zero-padding format (e.g., `00001`).
- **Define Reset Frequency**: Configure whether the sequence resets to the starting number periodically (e.g., Annually, Monthly, or Never) - critical for financial year-based numbering.
- **Deactivate / Activate Sequence**: Toggle the active status of a sequence to prevent it from being used for new records, while preserving historical assignments.

**Group 2: Sequence Assignment**
- **Assign to Document / Entity Type**: Map a specific sequence rule to a document type (e.g., "Sales Invoice") or master entity type (e.g., "Customer Master").
- **Subsidiary-Specific Assignment**: Configure sequences specific to a `subsidiary_id` (e.g., Subsidiary A uses `INV-A-001`, Subsidiary B uses `INV-B-001`), adhering to the multi-tenant architecture rule.
- **Define Default vs. Override Sequences**: Set a global default sequence for a document type while allowing subsidiary-level overrides.

**Group 3: Sequence Execution & Generation**
- **Generate Next Sequence Number (Atomic API)**: Core backend utility that atomically fetches and increments the next available number based on the configuration to prevent race conditions or duplicate IDs under high concurrency.
- **Dynamic Variable Parsing**: Support variables in prefixes/suffixes (e.g., `{YYYY}`, `{MM}`, `{SUB_CODE}`) that resolve dynamically during generation.
- **Preview Sequence Format**: UI functionality to display a preview of what the next generated number will look like based on the current configuration.

**Group 4: Sequence Maintenance & Audit**
- **Manual Sequence Counter Adjustment**: Allow highly privileged administrators to manually adjust the "current number" counter to skip numbers or recover from errors.
- **View Sequence Audit Log**: Track all changes made to sequence configurations, rule assignments, and any manual adjustments to the current counter.
- **Automated Period-End Reset Handling**: Backend mechanism that automatically evaluates and resets sequence counters for series configured with periodic reset rules when crossing period boundaries.
