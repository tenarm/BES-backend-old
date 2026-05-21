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

def main():
    parser = argparse.ArgumentParser(description="Upgrade, degrade, or customize a client's licensed modules.")
    parser.add_argument("--client-id", help="Client ID (e.g. test_custom)")
    parser.add_argument("--plan", choices=["1", "2", "3", "4", "basic", "pro", "premium", "custom"], help="New plan choice (1=Basic, 2=Pro, 3=Premium, 4=Custom)")
    parser.add_argument("--modules", help="Comma-separated list of modules for custom plan (only used if plan is custom/4)")
    
    args = parser.parse_args()
    
    print("=== BES Client License Upgrade/Degrade CLI ===")
    
    # 1. Resolve client_id
    client_id = args.client_id
    if not client_id:
        client_id = input("Enter client_id (e.g. test_custom): ").strip()
    if not client_id:
        print("Error: client_id is required.")
        return

    instance_dir = BASE_DIR / "instances" / client_id
    config_dir = instance_dir / "config"
    onboard_config_path = config_dir / "onboard_config.json"
    
    if not instance_dir.exists() or not onboard_config_path.exists():
        print(f"Error: Client instance '{client_id}' does not exist or has not been onboarded.")
        return

    # Load existing configuration
    with open(onboard_config_path, "r", encoding="utf-8") as f:
        current_config = json.load(f)
        
    client_name = current_config.get("client_name", client_id)
    database_url = current_config.get("database_url", "")
    current_modules = current_config.get("licensed_modules", [])
    
    print(f"\nTarget Client: {client_name} ({client_id})")
    print(f"Current Licensed Modules: {current_modules}")
    
    # 2. Load packages spec & master permissions
    if not PACKAGES_SPEC_PATH.exists():
        print(f"Error: packages.json spec not found at {PACKAGES_SPEC_PATH}")
        return
    if not CORE_ADMIN_PERMS_PATH.exists():
        print(f"Error: admin_permissions.json not found at {CORE_ADMIN_PERMS_PATH}")
        return
        
    with open(PACKAGES_SPEC_PATH, "r") as f:
        packages_data = json.load(f)["packages"]
        
    with open(CORE_ADMIN_PERMS_PATH, "r") as f:
        master_perms = json.load(f)
        
    all_modules = list(master_perms.keys())
    
    # 3. Resolve plan choice
    plan_choice = args.plan
    if not plan_choice:
        print("\nSubscription Packages:")
        print("1. Basic Plan")
        print("2. Pro Plan")
        print("3. Premium (Enterprise) Plan")
        print("4. Custom (Pick individual extensions manually)")
        plan_choice = input("\nSelect new subscription package (1-4): ").strip()
        
    # Map string plan names to 1-4
    plan_map = {
        "basic": "1",
        "pro": "2",
        "premium": "3",
        "custom": "4"
    }
    plan_choice = plan_map.get(plan_choice.lower(), plan_choice)
    
    licensed_modules = []
    filtered_perms = {}
    plan_name = "custom"
    
    if plan_choice == "1":
        # Basic Plan
        plan_name = "basic"
        plan = packages_data["basic"]
        plan_modules = plan["modules"]
        print(f"\nApplying Package: {plan['display_name']}")
        
        for mod, subfeats in plan_modules.items():
            if mod in all_modules:
                licensed_modules.append(mod)
                if subfeats == "*":
                    filtered_perms[mod] = master_perms[mod]
                else:
                    filtered_perms[mod] = {sf: master_perms[mod][sf] for sf in subfeats if sf in master_perms[mod]}
                    
    elif plan_choice == "2":
        # Pro Plan
        plan_name = "pro"
        plan = packages_data["pro"]
        plan_modules = plan["modules"]
        print(f"\nApplying Package: {plan['display_name']}")
        
        for mod, subfeats in plan_modules.items():
            if mod in all_modules:
                licensed_modules.append(mod)
                if subfeats == "*":
                    filtered_perms[mod] = master_perms[mod]
                else:
                    filtered_perms[mod] = {sf: master_perms[mod][sf] for sf in subfeats if sf in master_perms[mod]}
                    
    elif plan_choice == "3":
        # Premium/Enterprise Plan
        plan_name = "premium"
        print("\nApplying Package: Enterprise Premium Plan")
        licensed_modules = [m for m in all_modules if m not in ("core", "settings")]
        filtered_perms = dict(master_perms)
        
    elif plan_choice == "4":
        # Custom Plan
        custom_display_modules = [m for m in all_modules if m not in ("core", "settings")]
        custom_selections = args.modules
        
        if not custom_selections:
            print("\nAvailable Modules:")
            for i, mod in enumerate(custom_display_modules, 1):
                print(f"{i}. {mod}")
            selections_input = input("\nEnter comma-separated numbers of modules to license (e.g. 1,2,5): ").strip()
            indices = [int(idx.strip()) for idx in selections_input.split(",") if idx.strip().isdigit()]
            custom_licensed = [custom_display_modules[idx - 1] for idx in indices if 1 <= idx <= len(custom_display_modules)]
        else:
            # Parse modules from comma-separated string argument (could be name or indices)
            custom_licensed = []
            for token in custom_selections.split(","):
                token = token.strip()
                if token.isdigit():
                    idx = int(token)
                    if 1 <= idx <= len(custom_display_modules):
                        custom_licensed.append(custom_display_modules[idx - 1])
                elif token in custom_display_modules:
                    custom_licensed.append(token)
                    
        licensed_modules = custom_licensed
        for mod in licensed_modules:
            if mod in master_perms:
                filtered_perms[mod] = master_perms[mod]
    else:
        print(f"Error: Invalid package selection '{plan_choice}'.")
        return

    # Always include core and settings permissions and modules
    always_include = ["core", "settings"]
    for mod in always_include:
        if mod in all_modules:
            if mod not in licensed_modules:
                licensed_modules.append(mod)
            if mod not in filtered_perms:
                if plan_choice == "1" and "settings" in packages_data["basic"]["modules"]:
                    subfeats = packages_data["basic"]["modules"]["settings"]
                    filtered_perms["settings"] = {sf: master_perms["settings"][sf] for sf in subfeats if sf in master_perms["settings"]}
                elif plan_choice == "2" and "settings" in packages_data["pro"]["modules"]:
                    subfeats = packages_data["pro"]["modules"]["settings"]
                    filtered_perms["settings"] = {sf: master_perms["settings"][sf] for sf in subfeats if sf in master_perms["settings"]}
                else:
                    filtered_perms[mod] = master_perms[mod]

    # Load and merge custom client-specific permissions if present
    custom_perms_path = config_dir / "custom_permissions.json"
    if custom_perms_path.exists():
        print(f"Found client-specific custom permissions at {custom_perms_path}. Merging...")
        try:
            with open(custom_perms_path, "r", encoding="utf-8") as f:
                custom_perms = json.load(f)
            for custom_mod, custom_feats in custom_perms.items():
                if custom_mod not in licensed_modules:
                    licensed_modules.append(custom_mod)
                if custom_mod in filtered_perms:
                    filtered_perms[custom_mod].update(custom_feats)
                else:
                    filtered_perms[custom_mod] = custom_feats
            print("Successfully merged custom permissions.")
        except Exception as e:
            print(f"Warning: Failed to merge custom permissions ({e})")

    print(f"\nNew Licensed Extension Modules: {[m for m in licensed_modules if m not in ('core', 'settings')]}")

    # 4. Write updated configs
    now_iso = datetime.datetime.now().isoformat()
    registered_at = current_config.get("registered_at", now_iso)
    status = current_config.get("status", "active")
    has_custom = (plan_choice == "4") or custom_perms_path.exists()
    
    config_data = {
        "client_id": client_id,
        "client_name": client_name,
        "database_url": database_url,
        "plan": plan_name,
        "custom_config": has_custom,
        "status": status,
        "registered_at": registered_at,
        "updated_at": now_iso,
        "licensed_modules": licensed_modules
    }
    
    with open(onboard_config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"Updated {onboard_config_path}")
    
    admin_perms_path = config_dir / "admin_permissions.json"
    with open(admin_perms_path, "w", encoding="utf-8") as f:
        json.dump(filtered_perms, f, indent=2)
    print(f"Updated {admin_perms_path}")

    # 5. Re-generate pyproject.toml
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

    pyproject_path = instance_dir / "pyproject.toml"
    with open(pyproject_path, "w", encoding="utf-8") as f:
        f.write(pyproject_data)
    print(f"Re-generated {pyproject_path}")

    # 6. Rebuild .egg-info
    print(f"\nRebuilding '{client_id}' to generate new .egg-info...")
    try:
        subprocess.run(["pdm", "build"], cwd=instance_dir, check=True)
        print("Build successful.")
    except subprocess.CalledProcessError:
        print(f"Warning: Build failed. You may need to run `pdm build` manually inside instances/{client_id}.")

    # 7. Sync root workspace dependencies
    print("\nSyncing root workspace environment...")
    try:
        subprocess.run(["pdm", "lock", "-d"], cwd=BASE_DIR, check=True)
        subprocess.run(["pdm", "install", "-d"], cwd=BASE_DIR, check=True)
        print("Workspace environment synced successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to sync workspace environment automatically ({e}).")
        print("Please run `pdm lock -d && pdm install -d` manually in the root directory.")

    print("\nClient license update complete!")

if __name__ == "__main__":
    main()
