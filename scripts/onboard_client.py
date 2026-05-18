import os
import json
import argparse
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CORE_ADMIN_PERMS_PATH = BASE_DIR / "core" / "core" / "admin_permissions.json"

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
    
    # Load master permissions to get available modules
    with open(CORE_ADMIN_PERMS_PATH, "r") as f:
        master_perms = json.load(f)
        
    all_modules = list(master_perms.keys())
    
    print("\nAvailable Modules:")
    for i, mod in enumerate(all_modules, 1):
        print(f"{i}. {mod}")
        
    selections = input("\nEnter comma-separated numbers of modules to license (e.g. 1,2,5): ").strip()
    
    licensed_modules = []
    if selections:
        indices = [int(idx.strip()) for idx in selections.split(",") if idx.strip().isdigit()]
        for idx in indices:
            if 1 <= idx <= len(all_modules):
                licensed_modules.append(all_modules[idx - 1])
                
    # Always include core modules if they exist
    always_include = ["core", "settings"]
    for mod in always_include:
        if mod in all_modules and mod not in licensed_modules:
            licensed_modules.append(mod)
            
    print(f"\nLicensed Modules: {licensed_modules}")
    
    # Create directories
    config_dir = BASE_DIR / "instances" / client_id / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Write onboard_config.json
    config_data = {
        "client_id": client_id,
        "client_name": client_name,
        "database_url": database_url,
        "licensed_modules": licensed_modules
    }
    
    config_path = config_dir / "onboard_config.json"
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    print(f"Created {config_path}")
    
    # Filter and write admin_permissions.json
    filtered_perms = {mod: master_perms[mod] for mod in licensed_modules if mod in master_perms}
    admin_perms_path = config_dir / "admin_permissions.json"
    with open(admin_perms_path, "w") as f:
        json.dump(filtered_perms, f, indent=2)
    print(f"Created {admin_perms_path}")
    
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
    
    print("\nOnboarding complete!")

if __name__ == "__main__":
    main()
