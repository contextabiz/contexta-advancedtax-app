from __future__ import annotations

from typing import Any, Callable, TypedDict

from diagnostics.types import DiagnosticItem


DataDict = dict[str, float | int | bool]
RuleResultMap = dict[str, dict[str, Any]]


class SimpleDiagnosticRule(TypedDict):
    severity: str
    category: str
    message: str
    when: Callable[[dict[str, Any]], bool]


class DecisionDiagnosticRule(TypedDict):
    severity: str
    category: str
    message: str | None
    message_from_rule_id: str | None
    when: Callable[[dict[str, Any], dict[str, Any], RuleResultMap], bool]


def value(data: dict[str, Any], key: str) -> float:
    return float(data.get(key, 0.0) or 0.0)


def flag(data: dict[str, Any], key: str) -> bool:
    return bool(data.get(key, False))


def text(data: dict[str, Any], key: str) -> str:
    return str(data.get(key, "") or "")


def review_flag(decision: dict[str, Any], rule_id: str) -> bool:
    return rule_id in decision.get("review_flags", [])


def rule_present(rule_result_by_id: RuleResultMap, rule_id: str) -> bool:
    return rule_id in rule_result_by_id


def build_rule_result_map(decision: dict[str, Any]) -> RuleResultMap:
    return {str(item["id"]): item for item in decision.get("rule_results", [])}


def run_simple_rules(
    data: dict[str, Any],
    rules: list[SimpleDiagnosticRule],
) -> list[DiagnosticItem]:
    return [
        (rule["severity"], rule["category"], rule["message"])
        for rule in rules
        if rule["when"](data)
    ]


def run_decision_rules(
    *,
    data: dict[str, Any],
    decision: dict[str, Any],
    rules: list[DecisionDiagnosticRule],
) -> list[DiagnosticItem]:
    rule_result_by_id = build_rule_result_map(decision)
    checks: list[DiagnosticItem] = []
    for rule in rules:
        if not rule["when"](data, decision, rule_result_by_id):
            continue
        if rule["message_from_rule_id"] is not None:
            message = str(rule_result_by_id[rule["message_from_rule_id"]]["message"])
        else:
            message = str(rule["message"] or "")
        checks.append((rule["severity"], rule["category"], message))
    return checks
