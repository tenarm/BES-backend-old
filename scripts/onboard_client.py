import os
import json
import argparse
import shutil
import subprocess
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CORE_ADMIN_PERMS_PATH = BASE_DIR / "core" / "core" / "admin_permissions.json"
PACKAGES_SPEC_PATH = BASE_DIR / "core" / "core" / "packages.json"

def update_root_pyproject(client_id):
    pyproject_path = BASE_DIR / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Warning: Root pyproject.toml not found at {pyproject_path}")
        return False
        
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    client_entry_double = f'-e file:///${{PROJECT_ROOT}}/instances/{client_id}'
    client_entry_single = f"-e file:///${{PROJECT_ROOT}}/instances/{client_id}"
    if client_entry_double in content or client_entry_single in content:
        print(f"Root pyproject.toml already contains reference to {client_id}.")
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
        lines.insert(insert_idx, f"    \"{client_entry_single}\",")
        new_content = "\n".join(lines) + "\n"
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Added {client_id} to root pyproject.toml dev dependency group.")
        return True
    else:
        # Append new section
        with open(pyproject_path, "a", encoding="utf-8") as f:
            f.write(f"\n[dependency-groups]\ndev = [\n    \"{client_entry_single}\",\n]\n")
        print(f"Created [dependency-groups] and added {client_id} to root pyproject.toml.")
        return True

def main():
    print("=== BES Client Onboarding CLI ===")
    
    client_id = input("Enter client_id (e.g. msme_pool_1): ").strip()
    if not client_id:
        print("client_id is required.")
        return
        
    client_name = input("Enter client_name (e.g. MSME Pool 1): ").strip()
    
    default_db_url = f"sqlite+aiosqlite:///./instances/{client_id}/data/{client_id}.db"
    db_url_input = input(f"Enter database_url (default: {default_db_url}): ").strip()
    database_url = db_url_input if db_url_input else default_db_url
    
    # Load packages spec
    if not PACKAGES_SPEC_PATH.exists():
        print(f"Error: packages.json spec not found at {PACKAGES_SPEC_PATH}")
        return
        
    with open(PACKAGES_SPEC_PATH, "r") as f:
        packages_data = json.load(f)["packages"]
        
    # Load master permissions to get available modules
    with open(CORE_ADMIN_PERMS_PATH, "r") as f:
        master_perms = json.load(f)
        
    all_modules = list(master_perms.keys())
    
    print("\nSubscription Packages:")
    print("1. Basic Plan")
    print("2. Pro Plan")
    print("3. Premium (Enterprise) Plan")
    print("4. Custom (Pick individual extensions manually)")
    
    package_choice = input("\nSelect subscription package (1-4): ").strip()
    
    licensed_modules = []
    filtered_perms = {}
    plan_name = "custom"
    
    if package_choice == "1":
        # Basic
        plan_name = "basic"
        plan = packages_data["basic"]
        plan_modules = plan["modules"]
        print(f"\nSelected Package: {plan['display_name']}")
        
        for mod, subfeats in plan_modules.items():
            if mod in all_modules:
                licensed_modules.append(mod)
                if subfeats == "*":
                    filtered_perms[mod] = master_perms[mod]
                else:
                    filtered_perms[mod] = {sf: master_perms[mod][sf] for sf in subfeats if sf in master_perms[mod]}
                    
    elif package_choice == "2":
        # Pro
        plan_name = "pro"
        plan = packages_data["pro"]
        plan_modules = plan["modules"]
        print(f"\nSelected Package: {plan['display_name']}")
        
        for mod, subfeats in plan_modules.items():
            if mod in all_modules:
                licensed_modules.append(mod)
                if subfeats == "*":
                    filtered_perms[mod] = master_perms[mod]
                else:
                    filtered_perms[mod] = {sf: master_perms[mod][sf] for sf in subfeats if sf in master_perms[mod]}
                    
    elif package_choice == "3":
        # Premium
        plan_name = "premium"
        print("\nSelected Package: Enterprise Premium Plan")
        # Under premium, all modules are licensed
        licensed_modules = [m for m in all_modules if m not in ("core", "settings")]
        filtered_perms = dict(master_perms)
        
    else:
        # Custom
        print("\nAvailable Modules:")
        custom_display_modules = [m for m in all_modules if m not in ("core", "settings")]
        for i, mod in enumerate(custom_display_modules, 1):
            print(f"{i}. {mod}")
            
        selections = input("\nEnter comma-separated numbers of modules to license (e.g. 1,2,5): ").strip()
        
        custom_licensed = []
        if selections:
            indices = [int(idx.strip()) for idx in selections.split(",") if idx.strip().isdigit()]
            for idx in indices:
                if 1 <= idx <= len(custom_display_modules):
                    custom_licensed.append(custom_display_modules[idx - 1])
                    
        licensed_modules = custom_licensed
        # Custom unlocks all sub-features for the selected modules
        for mod in licensed_modules:
            if mod in master_perms:
                filtered_perms[mod] = master_perms[mod]
                
    # Always include core and settings permissions and modules
    always_include = ["core", "settings"]
    for mod in always_include:
        if mod in all_modules:
            if mod not in licensed_modules:
                licensed_modules.append(mod)
            if mod not in filtered_perms:
                if package_choice == "1" and "settings" in packages_data["basic"]["modules"]:
                    subfeats = packages_data["basic"]["modules"]["settings"]
                    filtered_perms["settings"] = {sf: master_perms["settings"][sf] for sf in subfeats if sf in master_perms["settings"]}
                elif package_choice == "2" and "settings" in packages_data["pro"]["modules"]:
                    subfeats = packages_data["pro"]["modules"]["settings"]
                    filtered_perms["settings"] = {sf: master_perms["settings"][sf] for sf in subfeats if sf in master_perms["settings"]}
                else:
                    filtered_perms[mod] = master_perms[mod]
                    
    # Check for client-specific custom permissions to merge
    custom_perms_path = BASE_DIR / "instances" / client_id / "config" / "custom_permissions.json"
    if custom_perms_path.exists():
        print(f"\nFound client-specific custom permissions at {custom_perms_path}. Merging...")
        try:
            with open(custom_perms_path, "r", encoding="utf-8") as f:
                custom_perms = json.load(f)
                
            for custom_mod, custom_feats in custom_perms.items():
                if custom_mod not in licensed_modules:
                    licensed_modules.append(custom_mod)
                    
                if custom_mod in filtered_perms:
                    print(f"  Merging custom features into existing module '{custom_mod}'...")
                    filtered_perms[custom_mod].update(custom_feats)
                else:
                    print(f"  Registering custom module '{custom_mod}' with custom features...")
                    filtered_perms[custom_mod] = custom_feats
            print("Successfully merged custom permissions.")
        except Exception as e:
            print(f"Warning: Failed to merge custom permissions ({e})")
            
    print(f"\nLicensed Extension Modules: {[m for m in licensed_modules if m not in ('core', 'settings')]}")
    
    # Create directories
    config_dir = BASE_DIR / "instances" / client_id / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Write onboard_config.json
    now_iso = datetime.datetime.now().isoformat()
    has_custom = (package_choice == "4") or custom_perms_path.exists()
    config_data = {
        "client_id": client_id,
        "client_name": client_name,
        "database_url": database_url,
        "plan": plan_name,
        "custom_config": has_custom,
        "status": "active",
        "registered_at": now_iso,
        "updated_at": now_iso,
        "licensed_modules": licensed_modules
    }
    
    config_path = config_dir / "onboard_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"Created {config_path}")
    
    # Filter and write admin_permissions.json
    admin_perms_path = config_dir / "admin_permissions.json"
    with open(admin_perms_path, "w", encoding="utf-8") as f:
        json.dump(filtered_perms, f, indent=2)
    print(f"Created {admin_perms_path}")
    
    # Generate pyproject.toml
    pyproject_data = f"""[project]
name = "{client_id.replace('_', '-')}"
version = "0.1.0"
description = "{client_name} Client Instance"
requires-python = ">=3.10"
dependencies = [
"""
    # Only declare dependencies for physical extensions present under extensions/
    for mod in licensed_modules:
        ext_path = BASE_DIR / "extensions" / mod
        if ext_path.exists():
            pyproject_data += f'    "{mod}",\n'
    pyproject_data += "]\n"

    pyproject_data += f"""
[build-system]
requires = ["setuptools>=61.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["{client_id}"]
"""

    instance_root = BASE_DIR / "instances" / client_id
    pyproject_path = instance_root / "pyproject.toml"
    with open(pyproject_path, "w", encoding="utf-8") as f:
        f.write(pyproject_data)
    print(f"Created {pyproject_path}")
    
    # Generate Dockerfile
    dockerfile_data = f"""FROM python:3.10-slim

# Install system dependencies & PDM
RUN pip install --no-cache-dir pdm

WORKDIR /app

# Copy monorepo workspace configuration files
COPY pyproject.toml pdm.lock ./

# Copy core, extensions, and the specific client instance folder
COPY core ./core
COPY extensions ./extensions
COPY instances/{client_id} ./instances/{client_id}

# Install production dependencies (resolving workspace links)
RUN pdm install --prod --no-editable

EXPOSE 8000

# Set pythonpath so Uvicorn can resolve import paths correctly
ENV PYTHONPATH="/app"

CMD ["pdm", "run", "uvicorn", "instances.{client_id}.{client_id}.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    dockerfile_path = instance_root / "Dockerfile"
    with open(dockerfile_path, "w", encoding="utf-8") as f:
        f.write(dockerfile_data)
    print(f"Created {dockerfile_path}")
    
    # Copy boilerplate template if it exists
    boilerplate_dir = BASE_DIR / "boiler-plate-instance" / "app_template"
    if boilerplate_dir.exists():
        target_app_dir = BASE_DIR / "instances" / client_id / client_id
        print(f"\nCopying boilerplate from {boilerplate_dir} to {target_app_dir}...")
        
        shutil.copytree(boilerplate_dir, target_app_dir, dirs_exist_ok=True)
        
        # Iterate over all .py files and replace {{client_id}} with actual client_id
        replaced_count = 0
        for root, dirs, files in os.walk(target_app_dir):
            for file in files:
                if file.endswith(".py"):
                    filepath = Path(root) / file
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    if "{{client_id}}" in content:
                        new_content = content.replace("{{client_id}}", client_id)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        replaced_count += 1
                        
        print(f"Templated {replaced_count} boilerplate files with client_id '{client_id}'.")
    else:
        print("\nSkipping boilerplate copying (boiler-plate-instance/app_template not found).")
    
    print(f"\nBuilding '{client_id}' to generate .egg-info...")
    try:
        subprocess.run(["pdm", "build"], cwd=instance_root, check=True)
        print("Build successful. .egg-info generated.")
    except subprocess.CalledProcessError:
        print(f"Warning: Auto-build failed. You may need to run `pdm build` manually inside instances/{client_id}.")
        
    print("\nUpdating root workspace pyproject.toml...")
    if update_root_pyproject(client_id):
        print("Syncing root workspace environment...")
        try:
            subprocess.run(["pdm", "lock", "-d"], cwd=BASE_DIR, check=True)
            subprocess.run(["pdm", "install", "-d"], cwd=BASE_DIR, check=True)
            print("Workspace environment synced successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to sync workspace environment automatically ({e}).")
            print("Please run `pdm lock -d && pdm install -d` manually in the root directory.")
            
    print("\nOnboarding complete!")

if __name__ == "__main__":
    main()