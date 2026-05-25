import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

def remove_from_root_pyproject(client_id):
    """
    Safely removes the client instance reference from the root pyproject.toml's dev group.
    """
    pyproject_path = BASE_DIR / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Warning: Root pyproject.toml not found at {pyproject_path}")
        return False
        
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.splitlines()
    new_lines = []
    removed = False
    
    for line in lines:
        # Match either single or double quotes around the instance package link
        if f"instances/{client_id}" in line:
            removed = True
            continue  # Skip this line to remove it
        new_lines.append(line)
        
    if removed:
        new_content = "\n".join(new_lines) + "\n"
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Removed {client_id} from root pyproject.toml dependency groups.")
        return True
    else:
        print(f"No reference to {client_id} found in root pyproject.toml.")
        return False

def main():
    print("=== BES Client Deboarding CLI ===")
    
    client_id = input("Enter client_id to deboard (e.g. abc): ").strip()
    if not client_id:
        print("client_id is required.")
        return
        
    instance_dir = BASE_DIR / "instances" / client_id
    if not instance_dir.exists():
        print(f"Warning: Client instance directory not found at {instance_dir}")
        print("We will still attempt to clean up any references in pyproject.toml.")
    
    # Force confirmation
    confirm = input(f"\nAre you absolutely sure you want to deboard '{client_id}'?\nThis will PERMANENTLY delete all code and configurations under instances/{client_id}! (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Deboarding cancelled.")
        return
        
    print(f"\nDeboarding client '{client_id}'...")
    
    # 1. Clean up root pyproject.toml
    pyproject_updated = remove_from_root_pyproject(client_id)
    
    # 2. Delete instance directory
    if instance_dir.exists():
        try:
            print(f"Deleting files and directory at {instance_dir}...")
            shutil.rmtree(instance_dir)
            print("Successfully deleted client instance directory.")
        except Exception as e:
            print(f"Error: Failed to delete client instance directory ({e})")
            
    # 3. Synchronize environment if pyproject was updated
    if pyproject_updated:
        print("\nSyncing root workspace environment...")
        try:
            subprocess.run(["pdm", "lock", "-d"], cwd=BASE_DIR, check=True)
            subprocess.run(["pdm", "install", "-d"], cwd=BASE_DIR, check=True)
            print("Workspace environment synced successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to sync workspace environment automatically ({e}).")
            print("Please run `pdm lock -d && pdm install -d` manually in the root directory to finish cleanup.")
            
    print("\nDeboarding complete!")

if __name__ == "__main__":
    main()
