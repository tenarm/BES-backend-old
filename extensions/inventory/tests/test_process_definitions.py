import pytest
from core.processes import PROCESS_DEFINITIONS


def test_process_definitions_load():
    # Verify that the dictionary contains the keys we expect
    assert "item_master_qualification" in PROCESS_DEFINITIONS
    assert "location_qualification" in PROCESS_DEFINITIONS
    
    # Check item master qualification definition structure
    item_process = PROCESS_DEFINITIONS["item_master_qualification"]
    assert item_process["processId"] == "item_master_qualification"
    assert item_process["module"] == "inventory"
    assert item_process["entity"] == "inventory_item"
    assert len(item_process["steps"]) > 0
    
    # Check location qualification definition structure
    loc_process = PROCESS_DEFINITIONS["location_qualification"]
    assert loc_process["processId"] == "location_qualification"
    assert loc_process["module"] == "inventory"
    assert loc_process["entity"] == "inventory_warehouse_location"
    assert len(loc_process["steps"]) == 3
    
    # Verify step details for location qualification
    steps = loc_process["steps"]
    assert steps[0]["id"] == "location_setup"
    assert steps[0]["type"] == "direct"
    assert steps[0]["statusEvent"] == "LOCATION_DRAFT_CREATED"
    
    assert steps[1]["id"] == "safety_compliance_audit"
    assert steps[1]["type"] == "approval"
    assert steps[1]["statusEvent"] == "LOCATION_SAFETY_AUDITED"
    assert steps[1]["requiredRole"] == "safety_inspector"
    assert "location_setup" in steps[1]["dependsOn"]
    assert steps[1]["requiredModule"] == "inventory"
    assert steps[1]["requiredFeature"] == "warehouse_location"
    
    assert steps[2]["id"] == "operations_release"
    assert steps[2]["type"] == "sequence"
    assert steps[2]["statusEvent"] == "LOCATION_ACTIVATED"
    assert "safety_compliance_audit" in steps[2]["dependsOn"]
