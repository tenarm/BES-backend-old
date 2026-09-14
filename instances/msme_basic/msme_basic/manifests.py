import importlib
import logging

from msme_basic.bootstrap import LICENSED_MODULES

logger = logging.getLogger(__name__)

# ─── Single-Pass Manifest Discovery ───────────────────────────────────────
_MODULE_MANIFESTS: dict[str, object | None] = {}

for _mod_name in LICENSED_MODULES:
    try:
        _manifest_mod = importlib.import_module(f"{_mod_name}.manifest")
        if hasattr(_manifest_mod, "manifest"):
            _MODULE_MANIFESTS[_mod_name] = _manifest_mod.manifest
            logger.info(f"Discovered manifest: {_mod_name}")
            continue
    except ImportError:
        pass
    # Legacy module (no manifest) — will use direct model/router import fallback
    _MODULE_MANIFESTS[_mod_name] = None
    logger.debug(f"No manifest found for {_mod_name}, will use legacy fallback")
