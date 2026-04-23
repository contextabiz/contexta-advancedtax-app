from diagnostics.types import DiagnosticItem
from eligibility import (
    build_eligibility_decision,
    build_postcalc_rules_diagnostics,
    build_rules_diagnostics,
)

from .rule_registry import (
    CONTEXT_DIAGNOSTIC_RULES,
    POSTCALC_DIAGNOSTIC_RULES,
)
from rule_engine import run_simple_rules


def collect_diagnostics(context: dict[str, float | int | bool]) -> list[DiagnosticItem]:
    checks: list[DiagnosticItem] = []

    eligibility_decision = build_eligibility_decision(
        tax_year=int(context.get("tax_year", 2025) or 2025),
        province=str(context.get("province", "") or ""),
        age=float(context.get("age", 0.0) or 0.0),
        raw_inputs=context,
        result=None,
    )

    checks.extend(run_simple_rules(context, CONTEXT_DIAGNOSTIC_RULES))
    checks.extend(build_rules_diagnostics(context=context, eligibility_decision=eligibility_decision))

    return checks


def collect_postcalc_diagnostics(result: dict[str, float]) -> list[DiagnosticItem]:
    checks: list[DiagnosticItem] = []

    checks.extend(build_postcalc_rules_diagnostics(result=result))
    checks.extend(run_simple_rules(result, POSTCALC_DIAGNOSTIC_RULES))

    return checks
