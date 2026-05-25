import os
import json
import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PACKAGES_SPEC_PATH = BASE_DIR / "core" / "core" / "packages.json"
CORE_ADMIN_PERMS_PATH = BASE_DIR / "core" / "core" / "admin_permissions.json"

def to_camel_case(snake_str):
    components = snake_str.split('_')
    return "".join(x.title() for x in components)

def update_root_pyproject(extension_id):
    pyproject_path = BASE_DIR / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Warning: Root pyproject.toml not found at {pyproject_path}")
        return False
        
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    ext_entry_double = f'-e file:///${{PROJECT_ROOT}}/extensions/{extension_id}'
    ext_entry_single = f"-e file:///${{PROJECT_ROOT}}/extensions/{extension_id}"
    
    if ext_entry_double in content or ext_entry_single in content:
        print(f"Root pyproject.toml already contains reference to extension '{extension_id}'.")
        return True
        
    lines = content.splitlines()
    in_dep_groups = False
    in_dev = False
    insert_idx = -1
    
    for i, line in enumerate(lines):
        trimmed = line.strip()
        if trimmed == "[dependency-groups]":
            in_dep_groups = True
            continue
        if in_dep_groups:
            if trimmed.startswith("[") and trimmed.endswith("]"):
                break
            if trimmed.startswith("dev = ["):
                in_dev = True
                continue
            if in_dev:
                if trimmed == "]":
                    insert_idx = i
                    break
                    
    if insert_idx != -1:
        # Use single quotes to match the core style
        lines.insert(insert_idx, f"    \"{ext_entry_single}\",")
        new_content = "\n".join(lines) + "\n"
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Added extension '{extension_id}' to root pyproject.toml dev group.")
        return True
    else:
        # Append new section
        with open(pyproject_path, "a", encoding="utf-8") as f:
            f.write(f'\n[dependency-groups]\ndev = [\n    "{ext_entry_single}",\n]\n')
        print(f"Created [dependency-groups] and added extension '{extension_id}' to root pyproject.toml.")
        return True

def update_packages_json(extension_id):
    if not PACKAGES_SPEC_PATH.exists():
        print(f"Warning: packages.json not found at {PACKAGES_SPEC_PATH}")
        return False
        
    with open(PACKAGES_SPEC_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Add to pro plan modules if not already present
    pro_modules = data.get("packages", {}).get("pro", {}).get("modules", {})
    if extension_id not in pro_modules:
        pro_modules[extension_id] = ["entity_management"]
        with open(PACKAGES_SPEC_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Registered module '{extension_id}' in packages.json (Professional Plan).")
    else:
        print(f"Module '{extension_id}' is already registered in packages.json.")
    return True

def update_admin_permissions_json(extension_id):
    if not CORE_ADMIN_PERMS_PATH.exists():
        print(f"Warning: admin_permissions.json not found at {CORE_ADMIN_PERMS_PATH}")
        return False
        
    with open(CORE_ADMIN_PERMS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Add module default CRUD permissions if not already present
    if extension_id not in data:
        data[extension_id] = {
            "entity_management": {
                "read": True,
                "write": True,
                "delete": True
            }
        }
        with open(CORE_ADMIN_PERMS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Registered default permissions for '{extension_id}' in admin_permissions.json.")
    else:
        print(f"Module '{extension_id}' already has permissions registered in admin_permissions.json.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Create a new BES backend extension module.")
    parser.add_argument("--id", help="The unique snake_case ID of the extension (e.g. procurement).")
    parser.add_argument("--name", help="The display name of the extension (e.g. Procurement).")
    parser.add_argument("--modular", action="store_true", help="Scaffold a modular directory structure instead of flat files.")
    args = parser.parse_args()
    
    print("=== BES Extension Creation CLI ===")
    
    extension_id = args.id
    if not extension_id:
        extension_id = input("Enter extension ID (snake_case, e.g. procurement): ").strip()
    if not extension_id:
        print("Error: extension ID is required.")
        return
        
    extension_name = args.name
    if not extension_name:
        extension_name = input("Enter extension display name (e.g. Procurement): ").strip()
    if not extension_name:
        extension_name = to_camel_case(extension_id)
        
    modular = args.modular
    if not args.id:
        mod_input = input("Use a modular directory structure? [y/N]: ").strip().lower()
        modular = modular or (mod_input in ["y", "yes"])
        
    extension_class = to_camel_case(extension_id)
    
    # Path setup
    ext_root = BASE_DIR / "extensions" / extension_id
    ext_pkg_dir = ext_root / extension_id
    
    if ext_root.exists():
        print(f"Error: Extension directory '{ext_root}' already exists. Aborting.")
        return
        
    # 1. Create directories
    ext_pkg_dir.mkdir(parents=True, exist_ok=False)
    print(f"Created directory: {ext_pkg_dir}")
    
    # 2. pyproject.toml
    pyproject_toml = ext_root / "pyproject.toml"
    pyproject_content = f"""[project]
name = "{extension_id}"
version = "0.1.0"
description = "{extension_name} Extension Module"
requires-python = ">=3.10"
dependencies = [
    "core"
]

[build-system]
requires = ["setuptools>=61.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["{extension_id}"]
"""
    with open(pyproject_toml, "w", encoding="utf-8") as f:
        f.write(pyproject_content)
    print(f"Created: {pyproject_toml}")
    
    # 3. __init__.py
    init_py = ext_pkg_dir / "__init__.py"
    with open(init_py, "w", encoding="utf-8") as f:
        f.write(f'"""{extension_name} Extension"""\n')
    print(f"Created: {init_py}")
    
    if modular:
        # Create package subdirectories
        (ext_pkg_dir / "models").mkdir(exist_ok=True)
        (ext_pkg_dir / "schemas").mkdir(exist_ok=True)
        (ext_pkg_dir / "services").mkdir(exist_ok=True)
        (ext_pkg_dir / "router").mkdir(exist_ok=True)
        
        # 4a. models/__init__.py
        with open(ext_pkg_dir / "models" / "__init__.py", "w", encoding="utf-8") as f:
            f.write(f"from .entity import {extension_class}Entity\n")
            
        # 4b. models/entity.py
        models_content = f"""import uuid
from sqlmodel import Field
from core.models import BESBase

class {extension_class}Entity(BESBase, table=True):
    __tablename__ = "{extension_id}_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
"""
        with open(ext_pkg_dir / "models" / "entity.py", "w", encoding="utf-8") as f:
            f.write(models_content)
        print(f"Created modular package: {ext_pkg_dir}/models")
            
        # 5a. schemas/__init__.py
        with open(ext_pkg_dir / "schemas" / "__init__.py", "w", encoding="utf-8") as f:
            f.write(f"from .entity import {extension_class}EntityCreate, {extension_class}EntityRead\n")
            
        # 5b. schemas/entity.py
        schemas_content = f"""import uuid
from typing import Optional
from sqlmodel import SQLModel

class {extension_class}EntityCreate(SQLModel):
    name: str
    description: str = ""

class {extension_class}EntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
"""
        with open(ext_pkg_dir / "schemas" / "entity.py", "w", encoding="utf-8") as f:
            f.write(schemas_content)
        print(f"Created modular package: {ext_pkg_dir}/schemas")
            
        # 6a. services/__init__.py
        with open(ext_pkg_dir / "services" / "__init__.py", "w", encoding="utf-8") as f:
            f.write("from .entity import create_entity\n")
            
        # 6b. services/entity.py
        services_content = f"""import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.entity import {extension_class}Entity
from ..schemas.entity import {extension_class}EntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: {extension_class}EntityCreate) -> {extension_class}Entity:
    db_obj = {extension_class}Entity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
"""
        with open(ext_pkg_dir / "services" / "entity.py", "w", encoding="utf-8") as f:
            f.write(services_content)
        print(f"Created modular package: {ext_pkg_dir}/services")
            
        # 7a. router/__init__.py
        router_init_content = f"""from fastapi import APIRouter
from .entity import router as entity_router

router = APIRouter(prefix="/api/v1/{extension_id}", tags=["{extension_id}"])
router.include_router(entity_router)

__all__ = ["router"]
"""
        with open(ext_pkg_dir / "router" / "__init__.py", "w", encoding="utf-8") as f:
            f.write(router_init_content)
            
        # 7b. router/entity.py
        router_content = f"""from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from ..models.entity import {extension_class}Entity
from ..schemas.entity import {extension_class}EntityCreate
from ..services.entity import create_entity
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission

router = APIRouter()

@router.get("/entities", dependencies=[Depends(require_permission("{extension_id}:entity:read"))])
async def list_entities(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("{extension_id}", "entity_management")

    count_stmt = select(func.count()).select_from({extension_class}Entity).where({extension_class}Entity.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select({extension_class}Entity)
        .where({extension_class}Entity.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/entities", dependencies=[Depends(require_permission("{extension_id}:entity:write"))])
async def create_entity_endpoint(
    data: {extension_class}EntityCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("{extension_id}", "entity_management")

    item = await create_entity(session, data)
    return success_response(data=item)
"""
        with open(ext_pkg_dir / "router" / "entity.py", "w", encoding="utf-8") as f:
            f.write(router_content)
        print(f"Created modular package: {ext_pkg_dir}/router")
    else:
        # 4. models.py
        models_py = ext_pkg_dir / "models.py"
        models_content = f"""import uuid
from sqlmodel import Field
from core.models import BESBase

class {extension_class}Entity(BESBase, table=True):
    __tablename__ = "{extension_id}_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
"""
        with open(models_py, "w", encoding="utf-8") as f:
            f.write(models_content)
        print(f"Created: {models_py}")
        
        # 5. schemas.py
        schemas_py = ext_pkg_dir / "schemas.py"
        schemas_content = f"""import uuid
from typing import Optional
from sqlmodel import SQLModel

class {extension_class}EntityCreate(SQLModel):
    name: str
    description: str = ""

class {extension_class}EntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
"""
        with open(schemas_py, "w", encoding="utf-8") as f:
            f.write(schemas_content)
        print(f"Created: {schemas_py}")
        
        # 6. services.py
        services_py = ext_pkg_dir / "services.py"
        services_content = f"""import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import {extension_class}Entity
from .schemas import {extension_class}EntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: {extension_class}EntityCreate) -> {extension_class}Entity:
    db_obj = {extension_class}Entity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
"""
        with open(services_py, "w", encoding="utf-8") as f:
            f.write(services_content)
        print(f"Created: {services_py}")
        
        # 7. router.py
        router_py = ext_pkg_dir / "router.py"
        router_content = f"""from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import {extension_class}Entity
from .schemas import {extension_class}EntityCreate
from .services import create_entity
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission

router = APIRouter(prefix="/api/v1/{extension_id}", tags=["{extension_id}"])

@router.get("/entities", dependencies=[Depends(require_permission("{extension_id}:entity:read"))])
async def list_entities(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("{extension_id}", "entity_management")

    count_stmt = select(func.count()).select_from({extension_class}Entity).where({extension_class}Entity.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select({extension_class}Entity)
        .where({extension_class}Entity.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/entities", dependencies=[Depends(require_permission("{extension_id}:entity:write"))])
async def create_entity_endpoint(
    data: {extension_class}EntityCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("{extension_id}", "entity_management")

    item = await create_entity(session, data)
    return success_response(data=item)
"""
        with open(router_py, "w", encoding="utf-8") as f:
            f.write(router_content)
        print(f"Created: {router_py}")
    
    # 8. events.py
    events_py = ext_pkg_dir / "events.py"
    events_content = f"""import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)

async def emit_entity_created(entity_id: str, entity_name: str):
    payload = BaseEventPayload(
        emitter_module="{extension_id}",
        event_type="{extension_id.upper()}_ENTITY_CREATED",
        data={{"entity_id": entity_id, "name": entity_name}}
    )
    await event_bus.emit(payload)

def register_event_handlers():
    logger.info("[{extension_name}] Event handlers registered")
"""
    with open(events_py, "w", encoding="utf-8") as f:
        f.write(events_content)
    print(f"Created: {events_py}")
    
    # 9. manifest.py
    manifest_py = ext_pkg_dir / "manifest.py"
    manifest_content = f"""from fastapi import APIRouter
from core.extension import ExtensionManifest

class {extension_class}Manifest(ExtensionManifest):
    @property
    def module_name(self) -> str:
        return "{extension_id}"

    def get_router(self) -> APIRouter:
        from .router import router
        return router

    def get_models(self) -> list[type]:
        from .models import {extension_class}Entity
        return [{extension_class}Entity]

    def get_event_handlers(self):
        from .events import register_event_handlers
        return register_event_handlers

manifest = {extension_class}Manifest()
"""
    with open(manifest_py, "w", encoding="utf-8") as f:
        f.write(manifest_content)
    print(f"Created: {manifest_py}")

    
    # 10. Update configurations
    update_root_pyproject(extension_id)
    update_packages_json(extension_id)
    update_admin_permissions_json(extension_id)
    
    # 11. Run build in extension dir
    print(f"\nBuilding '{extension_id}' to generate .egg-info...")
    try:
        subprocess.run(["pdm", "build"], cwd=ext_root, check=True)
        print("Build successful.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Extension build failed ({e}). Run `pdm build` manually inside extensions/{extension_id}.")
        
    # 12. Run workspace sync
    print("\nSyncing workspace environment...")
    try:
        subprocess.run(["pdm", "lock", "-d"], cwd=BASE_DIR, check=True)
        subprocess.run(["pdm", "install", "-d"], cwd=BASE_DIR, check=True)
        print("Workspace environment synced successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Workspace sync failed ({e}). Please run `pdm lock -d && pdm install -d` manually in the root directory.")
        
    print(f"\nExtension '{extension_id}' created successfully!")

if __name__ == "__main__":
    main()
