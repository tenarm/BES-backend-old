# bes-backend/core/core/processes.py
import os
import sys
import json
import copy
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Schema Definitions ---

class ActionDefinition(BaseModel):
    label: str
    api_endpoint: str = Field(..., alias="apiEndpoint")
    method: str

    class Config:
        populate_by_name = True
        alias_generator = None


class ProcessStep(BaseModel):
    id: str
    label: str
    type: str  # "direct" | "approval" | "sequence"
    status_event: str = Field(..., alias="statusEvent")
    depends_on: Optional[List[str]] = Field(default=None, alias="dependsOn")
    required_role: Optional[str] = Field(default=None, alias="requiredRole")
    required_module: Optional[str] = Field(default=None, alias="requiredModule")
    required_feature: Optional[str] = Field(default=None, alias="requiredFeature")
    description: Optional[str] = None
    action: Optional[ActionDefinition] = None

    class Config:
        populate_by_name = True
        alias_generator = None


class ProcessDefinition(BaseModel):
    process_id: str = Field(..., alias="processId")
    module: str
    label: str
    entity: str
    steps: List[ProcessStep]

    class Config:
        populate_by_name = True
        alias_generator = None


# --- Modular Dynamic Extension Loader ---

def _find_project_root() -> Optional[str]:
    """Helper to locate the parent project root containing 'core' and 'extensions'."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(current_dir, "extensions")) and os.path.exists(os.path.join(current_dir, "core")):
            return current_dir
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent
    return None


def _load_process_definitions() -> Dict[str, Dict[str, Any]]:
    """
    Loads and validates modular process definitions from:
    1. Standard extension directories (extensions/{ext_name}/{ext_name}/process_definitions/*.json)
    2. Optionally, core process definitions directory (core/core/process_definitions/*.json)
    """
    merged_defs: Dict[str, Any] = {}
    project_root = _find_project_root()

    if not project_root:
        logger.warning("Could not locate project root. Scanning only ENV overrides.")
    
    # Track directories to scan
    scan_dirs: List[str] = []

    # 1. Look in environment override if defined
    env_dir = os.environ.get("PROCESS_DEFINITIONS_DIR")
    if env_dir and os.path.exists(env_dir):
        scan_dirs.append(env_dir)

    # 2. Collect process_definitions folders from extensions
    if project_root:
        extensions_dir = os.path.join(project_root, "extensions")
        if os.path.exists(extensions_dir):
            for ext_name in os.listdir(extensions_dir):
                # Ensure it's a directory (not .DS_Store or files)
                if not os.path.isdir(os.path.join(extensions_dir, ext_name)):
                    continue
                # Extension package structure: extensions/{ext_name}/{ext_name}/process_definitions
                ext_defs_path = os.path.join(extensions_dir, ext_name, ext_name, "process_definitions")
                if os.path.exists(ext_defs_path) and os.path.isdir(ext_defs_path):
                    scan_dirs.append(ext_defs_path)

        # 3. Collect core process_definitions folder as fallback/base
        core_defs_path = os.path.join(project_root, "core", "core", "process_definitions")
        if os.path.exists(core_defs_path) and os.path.isdir(core_defs_path):
            scan_dirs.append(core_defs_path)

    # Scan and merge JSON files from gathered directories
    for dir_path in scan_dirs:
        logger.info(f"Scanning process definitions in: {dir_path}")
        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                file_path = os.path.join(dir_path, filename)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        merged_defs.update(data)
                except Exception as e:
                    logger.error(f"Failed to load process definition file {filename} in {dir_path}: {e}")

    # Validate structure using Pydantic models
    validated_models: Dict[str, ProcessDefinition] = {
        key: ProcessDefinition.parse_obj(val) if hasattr(ProcessDefinition, "parse_obj") else ProcessDefinition(**val)
        for key, val in merged_defs.items()
    }
    
    # Cast back to dictionary for consumer compatibility (FastAPI, JSON serialization)
    serialized_defs: Dict[str, Dict[str, Any]] = {}
    for key, model in validated_models.items():
        if hasattr(model, "model_dump"):
            serialized_defs[key] = model.model_dump(by_alias=True, exclude_none=True)
        else:
            serialized_defs[key] = model.dict(by_alias=True, exclude_none=True)
            
    return serialized_defs


# --- Dynamic License-Aware Filter and Dependency Resolver ---

def get_active_licensed_modules() -> Optional[List[str]]:
    """Tries to find the active client's LICENSED_MODULES from loaded sys.modules."""
    for module_name, module in list(sys.modules.items()):
        if module_name.startswith("instances.") and module_name.endswith(".bootstrap"):
            if hasattr(module, "LICENSED_MODULES"):
                return getattr(module, "LICENSED_MODULES")
    return None


def resolve_process_for_client(process_def_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dynamically filters process steps based on active licensing/permissions,
    and updates dependencies to ensure step chains remain intact.
    """
    from core.licensing import is_feature_licensed

    licensed_modules = get_active_licensed_modules()
    if licensed_modules is None:
        # Fallback if no instance is active (e.g. tests or standalone scripts)
        return process_def_dict

    # Copy definitions to avoid mutating global cache
    pdef = copy.deepcopy(process_def_dict)
    original_steps = pdef.get("steps", [])
    filtered_steps = []
    removed_step_ids = set()

    # Create dependency map
    dep_map = {}
    for step in original_steps:
        dep_map[step["id"]] = step.get("dependsOn") or []

    # 1. Filter out unlicensed steps
    for step in original_steps:
        # Check required module
        req_module = step.get("requiredModule")
        if req_module and req_module not in licensed_modules:
            removed_step_ids.add(step["id"])
            continue

        # Check required granular feature
        req_feature = step.get("requiredFeature")
        if req_feature:
            module_to_check = req_module or pdef.get("module")
            if not is_feature_licensed(module_to_check, req_feature):
                removed_step_ids.add(step["id"])
                continue

        filtered_steps.append(step)

    # 2. Re-route dependencies dynamically
    for step in filtered_steps:
        depends_on = step.get("dependsOn")
        if not depends_on:
            continue

        new_depends = []
        for dep in depends_on:
            resolved_deps = _resolve_dependency(dep, removed_step_ids, dep_map)
            new_depends.extend(resolved_deps)

        # Apply resolved, de-duplicated deps
        step["dependsOn"] = list(set(new_depends))

    pdef["steps"] = filtered_steps
    return pdef


def _resolve_dependency(dep_id: str, removed_ids: set[str], dep_map: dict) -> list[str]:
    """Recursively resolves dependencies when intermediate steps are skipped."""
    if dep_id not in removed_ids:
        return [dep_id]
        
    parent_deps = dep_map.get(dep_id, [])
    resolved = []
    for parent in parent_deps:
        resolved.extend(_resolve_dependency(parent, removed_ids, dep_map))
    return resolved


# Global Single Source of Truth Definitions Map
PROCESS_DEFINITIONS = _load_process_definitions()
