import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def _bootstrap_config():
    """
    Reads the client onboarding config, resolves paths, and injects environment
    variables. Must be called before any core imports.

    Returns: (client_config dict, licensed_modules list, BASE_DIR Path)
    """
    import sys

    BASE_DIR = Path(__file__).resolve().parents[3]
    logger.info(f"BASE_DIR resolved to {BASE_DIR}")

    # Workspace members on sys.path (simulates editable installs in dev)
    core_path = str(BASE_DIR / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)

    import os
    
    CONFIG_PATH = BASE_DIR / "instances" / "msme_premium" / "config" / "onboard_config.json"
    os.environ["ADMIN_PERMISSIONS_PATH"] = str(BASE_DIR / "instances" / "msme_premium" / "config" / "admin_permissions.json")
    
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    licensed_modules = config.get("licensed_modules", [])

    for mod in licensed_modules:
        ext_path = BASE_DIR / "extensions" / mod
        if ext_path.exists():
            ext_str = str(ext_path)
            if ext_str not in sys.path:
                sys.path.insert(0, ext_str)

    # Resolve database URL (SQLite relative → absolute)
    db_url = config.get("database_url", "sqlite+aiosqlite:///./default.db")
    if ":///" in db_url and not db_url.startswith("postgresql"):
        prefix, path = db_url.rsplit("///", 1)
        abs_path = str(BASE_DIR / path)
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        db_url = f"{prefix}///{abs_path}"

    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault(
        "JWT_SECRET_KEY",
        "dev-only-secret-change-in-production-" + config.get("client_id", "default")
    )

    return config, licensed_modules, BASE_DIR

CLIENT_CONFIG, LICENSED_MODULES, BASE_DIR = _bootstrap_config()
