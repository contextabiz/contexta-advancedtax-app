from __future__ import annotations

from typing import Any


def value(data: dict[str, Any], key: str) -> float:
    return float(data.get(key, 0.0) or 0.0)


def calculate_progressive_tax(income: float, brackets) -> float:
    tax = 0.0
    previous_limit = 0.0

    for limit, rate in brackets:
        if income <= previous_limit:
            break
        taxable_amount = min(income, limit) - previous_limit
        tax += taxable_amount * rate
        previous_limit = limit

    return max(0.0, tax)


def calculate_federal_bpa(net_income: float, params: dict[str, Any]) -> float:
    max_bpa = params["federal_bpa_max"]
    min_bpa = params["federal_bpa_min"]
    start = params["federal_bpa_phaseout_start"]
    end = params["federal_bpa_phaseout_end"]

    if net_income <= start:
        return max_bpa
    if net_income >= end:
        return min_bpa

    reduction = ((net_income - start) / (end - start)) * (max_bpa - min_bpa)
    return max_bpa - reduction


def estimate_employee_cpp_ei(employment_income: float, params: dict[str, Any]) -> dict[str, float]:
    contributory_earnings = max(0.0, min(employment_income, params["cpp_ympe"]) - params["cpp_basic_exemption"])
    contributory_earnings = min(contributory_earnings, params["cpp_max_contributory_earnings"])

    cpp_base = contributory_earnings * params["cpp_base_rate"]
    cpp_first_additional = contributory_earnings * params["cpp_first_additional_rate"]

    cpp2_earnings = max(0.0, min(employment_income, params["cpp_yampe"]) - params["cpp_ympe"])
    cpp2 = cpp2_earnings * params["cpp2_rate"]

    if employment_income <= 2000:
        ei = 0.0
    else:
        ei = min(employment_income, params["ei_max_insurable_earnings"]) * params["ei_rate"]

    return {
        "employee_cpp_base": cpp_base,
        "employee_cpp_enhanced": cpp_first_additional + cpp2,
        "employee_cpp_total": cpp_base + cpp_first_additional + cpp2,
        "ei": ei,
    }
