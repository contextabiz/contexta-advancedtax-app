from diagnostics.types import DiagnosticItem

from .rule_registry import (
    ELIGIBILITY_DIAGNOSTIC_RULES,
    ELIGIBILITY_POSTCALC_RULES,
)
from .types import EligibilityDecision
from rule_engine import run_decision_rules, run_simple_rules


def build_rules_diagnostics(
    *,
    context: dict[str, float | int | bool],
    eligibility_decision: EligibilityDecision,
) -> list[DiagnosticItem]:
    return run_decision_rules(data=context, decision=eligibility_decision, rules=ELIGIBILITY_DIAGNOSTIC_RULES)


def build_postcalc_rules_diagnostics(
    *,
    result: dict[str, float],
) -> list[DiagnosticItem]:
    return run_simple_rules(result, ELIGIBILITY_POSTCALC_RULES)
