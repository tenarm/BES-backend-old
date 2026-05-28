"""
Flow Engine — Condition evaluator for decision steps.

Evaluates conditions defined in flow step schemas against
entity data to determine the next step in the pipeline.

Supported operators: ==, !=, >, <, >=, <=, in, not_in, is_empty, is_not_empty
Field paths support dot notation: e.g., 'customer.credit_limit'
"""
from typing import Any
import logging
import operator as op

logger = logging.getLogger(__name__)

# Operator mapping
OPERATORS = {
    "==": op.eq,
    "!=": op.ne,
    ">": op.gt,
    "<": op.lt,
    ">=": op.ge,
    "<=": op.le,
}


def _resolve_field_path(data: dict[str, Any], path: str) -> Any:
    """
    Resolve a dot-notation field path against a data dictionary.

    Examples:
        _resolve_field_path({"customer": {"credit_limit": 5000}}, "customer.credit_limit")
        → 5000
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
        if current is None:
            return None
    return current


def evaluate_condition(condition: dict[str, Any], entity_data: dict[str, Any]) -> bool:
    """
    Evaluate a single condition against entity data.

    Args:
        condition: Dict with 'field', 'operator', and 'value' keys.
        entity_data: The entity's current data as a dictionary.

    Returns:
        True if the condition is met, False otherwise.

    Examples:
        evaluate_condition(
            {"field": "total_amount", "operator": ">", "value": 10000},
            {"total_amount": 15000}
        )
        → True
    """
    field_path = condition.get("field", "")
    condition_operator = condition.get("operator", "==")
    expected_value = condition.get("value")

    actual_value = _resolve_field_path(entity_data, field_path)

    try:
        if condition_operator == "in":
            return actual_value in (expected_value or [])

        elif condition_operator == "not_in":
            return actual_value not in (expected_value or [])

        elif condition_operator == "is_empty":
            return actual_value is None or actual_value == "" or actual_value == []

        elif condition_operator == "is_not_empty":
            return actual_value is not None and actual_value != "" and actual_value != []

        elif condition_operator in OPERATORS:
            if actual_value is None:
                return False
            # Attempt numeric comparison if both values look numeric
            try:
                actual_numeric = float(actual_value)
                expected_numeric = float(expected_value)
                return OPERATORS[condition_operator](actual_numeric, expected_numeric)
            except (ValueError, TypeError):
                return OPERATORS[condition_operator](actual_value, expected_value)

        else:
            logger.warning(f"Unknown operator: {condition_operator}")
            return False

    except Exception as e:
        logger.error(f"Error evaluating condition {condition}: {e}")
        return False


def evaluate_decision_step(
    conditions: list[dict[str, Any]],
    entity_data: dict[str, Any],
    default_next: str | None = None,
) -> str | None:
    """
    Evaluate all conditions of a decision step and return the next step ID.

    Conditions are evaluated top-to-bottom; first match wins.
    Falls back to `default_next` if no condition matches.

    Args:
        conditions: List of condition dicts, each with 'if' and 'then' keys.
        entity_data: The entity's current data.
        default_next: Fallback step ID if no condition matches.

    Returns:
        The step ID to transition to, or None.
    """
    for cond_block in conditions:
        if_condition = cond_block.get("if", {})
        then_step = cond_block.get("then")

        if evaluate_condition(if_condition, entity_data):
            return then_step

    return default_next
