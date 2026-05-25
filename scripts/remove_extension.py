import os
import json
import argparse
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PACKAGES_SPEC_PATH = BASE_DIR / "core" / "core" / "packages.json"
CORE_ADMIN_PERMS_PATH = BASE_DIR / "core" / "core" / "admin_permissions.json"

def update_root_pyproject(extension_id):
    pyproject_path = BASE_DIR / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Warning: Root pyproject.toml not found at {pyproject_path}")
        return False
        
    with open(pyproject_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    new_lines = []
    removed = False
    for line in lines:
        if f"extensions/{extension_id}" in line:
            removed = True
            continue
        new_lines.append(line)
        
    if removed:
        # Clean up any potential double trailing commas/newlines that result from line deletion
        content = "".join(new_lines)
        # Standardize formatting
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Removed extension '{extension_id}' from root pyproject.toml dev group.")
    else:
        print(f"Extension '{extension_id}' reference not found in root pyproject.toml.")
    return True

def update_packages_json(extension_id):
    if not PACKAGES_SPEC_PATH.exists():
        print(f"Warning: packages.json not found at {PACKAGES_SPEC_PATH}")
        return False
        
    with open(PACKAGES_SPEC_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    modified = False
    packages = data.get("packages", {})
    for plan in packages.values():
        modules = plan.get("modules", {})
        if isinstance(modules, dict) and extension_id in modules:
            del modules[extension_id]
            modified = True
            
    if modified:
        with open(PACKAGES_SPEC_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Unregistered module '{extension_id}' from packages.json.")
    else:
        print(f"Module '{extension_id}' not found in packages.json.")
    return True

def update_admin_permissions_json(extension_id):
    if not CORE_ADMIN_PERMS_PATH.exists():
        print(f"Warning: admin_permissions.json not found at {CORE_ADMIN_PERMS_PATH}")
        return False
        
    with open(CORE_ADMIN_PERMS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if extension_id in data:
        del data[extension_id]
        with open(CORE_ADMIN_PERMS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Unregistered permissions for '{extension_id}' in admin_permissions.json.")
    else:
        print(f"Permissions for module '{extension_id}' not found in admin_permissions.json.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Remove an existing BES backend extension module.")
    parser.add_argument("--id", help="The unique snake_case ID of the extension (e.g. procurement).")
    parser.add_argument("--force", action="store_true", help="Bypass interactive delete confirmations.")
    args = parser.parse_args()
    
    print("=== BES Extension Deletion CLI ===")
    
    extension_id = args.id
    if not extension_id:
        extension_id = input("Enter extension ID to remove (snake_case, e.g. procurement): ").strip()
    if not extension_id:
        print("Error: extension ID is required.")
        return

    # Check if standard directories exist
    ext_root = BASE_DIR / "extensions" / extension_id
    if not ext_root.exists() and not args.force:
        print(f"Warning: Extension directory '{ext_root}' does not exist.")
        confirm_continue = input("Do you still want to proceed with config cleanup? [y/N]: ").strip().lower()
        if confirm_continue not in ["y", "yes"]:
            print("Aborted.")
            return

    # Deletion Confirmation
    if not args.force and ext_root.exists():
        confirm = input(f"Are you sure you want to completely delete extension '{extension_id}'? This will permanently delete all its files! [y/N]: ").strip().lower()
        if confirm not in ["y", "yes"]:
            print("Aborted.")
            return
            
    # 1. Delete directory
    if ext_root.exists():
        shutil.rmtree(ext_root)
        print(f"Deleted directory: {ext_root}")
    
    # 2. Revert configurations
    update_root_pyproject(extension_id)
    update_packages_json(extension_id)
    update_admin_permissions_json(extension_id)
    
    # 3. Run workspace sync
    print("\nSyncing workspace environment...")
    try:
        subprocess.run(["pdm", "lock", "-d"], cwd=BASE_DIR, check=True)
        subprocess.run(["pdm", "install", "-d"], cwd=BASE_DIR, check=True)
        print("Workspace environment synced successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Workspace sync failed ({e}). Please run `pdm lock -d && pdm install -d` manually in the root directory.")
        
    print(f"\nExtension '{extension_id}' removed successfully!")

if __name__ == "__main__":
    main()
