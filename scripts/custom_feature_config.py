import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

def main():
    print("=== BES Custom Feature Permissions Builder ===")
    
    # 1. Prompt for client_id and show list of existing instances
    instances_dir = BASE_DIR / "instances"
    existing_instances = []
    if instances_dir.exists():
        existing_instances = [d.name for d in instances_dir.iterdir() if d.is_dir()]
        
    if existing_instances:
        print("\nExisting client instances:")
        for idx, inst in enumerate(existing_instances, 1):
            print(f"  {idx}. {inst}")
            
    client_id = input("\nEnter client_id (e.g. acme_corp): ").strip()
    if not client_id:
        print("Error: client_id is required.")
        return
        
    # 2. Prompt for custom module/extension name
    module_name = input("Enter custom module/extension name (e.g. sap_integration): ").strip().lower()
    if not module_name:
        print("Error: custom module name is required.")
        return
        
    # 3. Prompt for comma-separated feature list
    features_input = input("Enter comma-separated features/sub-features (e.g. sync, logs, config): ").strip()
    if not features_input:
        print("Error: At least one feature is required.")
        return
        
    features = [f.strip().lower() for f in features_input.split(",") if f.strip()]
    if not features:
        print("Error: No valid features specified.")
        return
        
    print(f"\nCustom Module: {module_name}")
    print(f"Custom Features: {features}")
    
    # Define paths
    config_dir = BASE_DIR / "instances" / client_id / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    custom_perms_path = config_dir / "custom_permissions.json"
    
    # Load existing custom permissions if they exist
    existing_custom_perms = {}
    if custom_perms_path.exists():
        try:
            with open(custom_perms_path, "r", encoding="utf-8") as f:
                existing_custom_perms = json.load(f)
            print(f"Loaded existing custom permissions from {custom_perms_path}")
        except Exception as e:
            print(f"Warning: Failed to load existing custom permissions ({e}). Creating new.")
            
    # Build new permission structure
    new_module_perms = {}
    for feat in features:
        new_module_perms[feat] = {
            "read": True,
            "write": True,
            "delete": True
        }
        
    # Merge new module permissions into existing custom permissions
    if module_name in existing_custom_perms:
        print(f"Merging new features into existing module '{module_name}'...")
        existing_custom_perms[module_name].update(new_module_perms)
    else:
        existing_custom_perms[module_name] = new_module_perms
        
    # Write custom_permissions.json
    try:
        with open(custom_perms_path, "w", encoding="utf-8") as f:
            json.dump(existing_custom_perms, f, indent=2)
        print(f"\nSuccess! Successfully updated {custom_perms_path}")
        print("New permission mapping schema:")
        print(json.dumps({module_name: new_module_perms}, indent=2))
    except Exception as e:
        print(f"Error: Failed to write to {custom_perms_path} ({e})")

if __name__ == "__main__":
    main()
