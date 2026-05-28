"""
core.licensing
==============
Subscription tier enforcement for the TenArm platform.

Responsibilities:
  - Load the canonical packages.json tier config on startup.
  - Resolve cumulative feature sets per tier (inheritance: premium ⊇ pro ⊇ basic).
  - Expose `is_feature_licensed()` and `require_licensed_feature()` for use in
    router and service layers.

Two licensing namespaces (see packages.json):
  - "modules"  → API-layer checks: `require_licensed_feature("sales", "orders")`
  - "flows"    → UX-layer checks:  `require_licensed_feature("sell", "quotations", namespace="flows")`

Usage:
    from core.licensing import require_licensed_feature, LicensingError

    # In a router (raises HTTP 403 on failure):
    require_licensed_feature("sales", "quotations")

    # In a background worker (raises LicensingError on failure):
    require_licensed_feature("money", "journal_entries", namespace="flows")
"""

import json
import logging
import os
from typing import Literal

from fastapi import HTTPException, status

from core.rbac import execution_context, ExecutionContextType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier configuration loader
# ---------------------------------------------------------------------------

_PACKAGES_PATH = os.path.join(os.path.dirname(__file__), "packages.json")

# Ordered from least to most permissive — used for inheritance resolution.
_TIER_ORDER: list[str] = ["basic", "pro", "premium"]


def _load_raw_packages() -> dict:
    """Reads packages.json from disk and returns the raw dictionary."""
    with open(_PACKAGES_PATH, "r") as f:
        return json.load(f)


def _resolve_features_for_tier(
    raw_packages: dict, tier: str
) -> dict[str, dict[str, list[str]]]:
    """
    Builds the cumulative feature set for a given tier by merging all tiers
    at or below it in the inheritance chain.

    Example:
        For tier="pro", returns the combined features of basic + pro.
        For tier="premium", returns the combined features of basic + pro + premium.

    Returns a structure:
        {
          "modules": { "sales": ["orders", "quotations", ...], ... },
          "flows":   { "sell":  ["quotations", "invoices", ...], ... }
        }
    """
    if tier not in _TIER_ORDER:
        raise ValueError(
            f"Unknown tier '{tier}'. Valid tiers: {_TIER_ORDER}. "
            "Check the tenant's subscription configuration."
        )

    # Determine which tiers contribute to this tier (all tiers up to and including it)
    contributing_tiers = _TIER_ORDER[: _TIER_ORDER.index(tier) + 1]

    resolved: dict[str, dict[str, list[str]]] = {"modules": {}, "flows": {}}

    for t in contributing_tiers:
        tier_config = raw_packages.get("packages", {}).get(t, {})
        for namespace in ("modules", "flows"):
            namespace_config = tier_config.get(namespace, {})
            for module_key, features in namespace_config.items():
                if module_key not in resolved[namespace]:
                    resolved[namespace][module_key] = []
                # Merge feature list, avoiding duplicates
                for feature in features:
                    if feature not in resolved[namespace][module_key]:
                        resolved[namespace][module_key].append(feature)

    return resolved


# ---------------------------------------------------------------------------
# Module-level cache: resolved feature sets keyed by tier name.
# Populated lazily on first access.
# ---------------------------------------------------------------------------

_raw_packages: dict | None = None
_resolved_cache: dict[str, dict] = {}


def _get_resolved(tier: str) -> dict[str, dict[str, list[str]]]:
    """Returns the cached resolved feature set for a tier, loading on first call."""
    global _raw_packages, _resolved_cache

    if _raw_packages is None:
        _raw_packages = _load_raw_packages()

    if tier not in _resolved_cache:
        _resolved_cache[tier] = _resolve_features_for_tier(_raw_packages, tier)

    return _resolved_cache[tier]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class LicensingError(Exception):
    """
    Raised when a feature is accessed outside the tenant's licensed tier.

    Use in non-web contexts (background workers, event handlers) where raising
    an HTTPException would be inappropriate.
    """
    pass


def is_feature_licensed(
    module: str,
    subfeature: str,
    namespace: Literal["modules", "flows"] = "modules",
    tier: str | None = None,
) -> bool:
    """
    Checks whether a specific sub-feature is licensed for the given tier.

    Args:
        module:     The module or flow ID to check (e.g. "sales", "sell").
        subfeature: The granular feature within that module (e.g. "orders", "quotations").
        namespace:  "modules" (API-layer enforcement, default) or "flows" (UX-layer gate).
        tier:       The tenant's subscription tier ("basic", "pro", "premium").
                    If None, bypasses the packages.json check and defers to the
                    SYSTEM context bypass below. In a real multi-tenant setup this
                    would be read from the active request's tenant context.

    Returns:
        True if licensed, False otherwise.

    Bypass conditions:
        - SYSTEM execution context (event handlers, background workers with elevate_context).
        - module == "core" (core services are always available).
        - tier is None (temporary: during development before tenant context is wired).
    """
    # SYSTEM context: privileged background routines bypass all licensing checks.
    if execution_context.get() == ExecutionContextType.SYSTEM:
        return True

    # Core services are always available regardless of tier.
    if module == "core":
        return True

    # When no tier is provided the check is bypassed. This supports development
    # environments where tenant context has not yet been wired into the request
    # lifecycle. Wire the tenant tier into JWT/session context to enforce licensing.
    if tier is None:
        logger.debug(
            "is_feature_licensed called without a tier — bypassing check. "
            "Wire tenant tier into request context to enforce licensing."
        )
        return True

    resolved = _get_resolved(tier)
    namespace_features = resolved.get(namespace, {})
    module_features = namespace_features.get(module, [])

    licensed = subfeature in module_features

    if not licensed:
        logger.debug(
            f"Feature '{namespace}.{module}:{subfeature}' is NOT licensed under tier='{tier}'."
        )

    return licensed


def require_licensed_feature(
    module: str,
    subfeature: str,
    namespace: Literal["modules", "flows"] = "modules",
    tier: str | None = None,
):
    """
    Asserts that a sub-feature is licensed, raising an appropriate exception if not.

    In a web request context, raises HTTP 403 Forbidden (automatically handled by FastAPI).
    In a background/worker context, raises LicensingError.

    Args:
        module:     The module or flow ID (e.g. "sales", "sell").
        subfeature: The granular feature (e.g. "orders", "quotations").
        namespace:  "modules" (default) or "flows".
        tier:       The tenant's subscription tier. See is_feature_licensed().

    Example (router):
        require_licensed_feature("sales", "quotations")

    Example (flow gate):
        require_licensed_feature("sell", "quotations", namespace="flows")
    """
    if not is_feature_licensed(module, subfeature, namespace=namespace, tier=tier):
        err_msg = (
            f"Subscription Restriction: '{namespace}.{module}:{subfeature}' is not available "
            "under your current plan. Upgrade to access this feature."
        )
        logger.warning(err_msg)

        # Raise the appropriate exception type based on execution context.
        # In a web request context the router layer expects HTTPException (→ HTTP 403).
        # In background workers and event handlers, LicensingError is raised so callers
        # can decide how to handle it without receiving a web-specific exception.
        if execution_context.get() == ExecutionContextType.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=err_msg,
            )
        raise LicensingError(err_msg)


def get_licensed_modules(tier: str, namespace: Literal["modules", "flows"] = "modules") -> list[str]:
    """
    Returns the list of all module/flow keys licensed under a given tier.

    Useful for filtering RBAC permission schemas to only show licensed modules.

    Args:
        tier:      The subscription tier ("basic", "pro", "premium").
        namespace: "modules" or "flows".

    Returns:
        List of licensed module/flow ID strings.
    """
    resolved = _get_resolved(tier)
    return list(resolved.get(namespace, {}).keys())
