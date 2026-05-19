# 1. Module & Feature Name
**Module:** Settings
**Feature:** Company / Entity Setup

# 2. Core Purpose
Manages the foundational corporate hierarchy (root company, subsidiaries, branches) to establish the multi-tenant `subsidiary_id` context. This ensures secure data isolation, centralized reporting, and accurate localized compliance across all BES modules.

# 3. Functionality Groups
- Entity Hierarchy Management
- Localization & Defaults
- Lifecycle Management

# 4. Detailed Functionalities List

*Entity Hierarchy Management*
- **Create Root Company:** Initialize the top-level organization (can only be done once if no root exists).
- **Add Subsidiary:** Create a child organization linked to a parent entity, automatically inheriting top-level rules but allowing localized overrides.
- **Add Branch:** Create an operational branch under a subsidiary.
- **View Corporate Hierarchy:** Visualize the parent-child entity relationships in an interactive tree structure.

*Localization & Defaults*
- **Set Base Currency:** Define the default functional currency for an entity, which acts as the foundation for the Finance module's "Money Rule".
- **Configure Regional Context:** Assign timezones and localized address structures.
- **Define Legal & Tax Registration:** Store official Tax IDs (e.g., EIN, VAT) and statutory registration numbers.

*Lifecycle Management*
- **Update Entity Details:** Modify the legal name, address, or tax details of an existing entity.
- **Deactivate/Suspend Entity:** Soft delete an entity to prevent new transactions while preserving historical data. Validates that no active children exist before allowing suspension.
- **Transfer/Re-parent Entity:** Move a subsidiary or branch under a new parent entity, enforcing strict cycle detection to prevent infinite hierarchy loops.
