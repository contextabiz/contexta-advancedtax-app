from .types import EligibilityContext, EligibilityRuleResult


def evaluate_cwb_eligibility(ctx: EligibilityContext) -> list[EligibilityRuleResult]:
    results: list[EligibilityRuleResult] = []

    if ctx["working_income"] <= 3000.0:
        results.append({
            "id": "cwb_below_working_income_threshold",
            "category": "refundable_credits",
            "status": "blocked",
            "message": "Working income is at or below the basic CWB working-income threshold.",
            "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "affects": ["cwb"],
        })
    elif (
        not ctx["cwb_basic_eligible"]
        and (
            ctx["cwb_preview_amount"] > 0.0
            or (
                ctx["cwb_no_basic_amount_above"] > 0.0
                and (ctx["adjusted_net_income"] + ctx["spouse_adjusted_net_income"]) <= ctx["cwb_no_basic_amount_above"]
            )
        )
    ):
        results.append({
            "id": "cwb_not_enabled",
            "category": "refundable_credits",
            "status": "review",
            "message": "CWB has not been enabled yet. The amount will not be added automatically unless you tick Eligible for CWB.",
            "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "affects": ["cwb"],
        })
    elif not ctx["cwb_basic_eligible"]:
        results.append({
            "id": "cwb_out_of_range_or_not_enabled",
            "category": "refundable_credits",
            "status": "allowed",
            "message": "CWB is not enabled, and the current income range does not clearly point to a CWB amount.",
            "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "affects": ["cwb"],
        })
    else:
        results.append({
            "id": "cwb_enabled",
            "category": "refundable_credits",
            "status": "allowed",
            "message": "CWB has been enabled for automatic estimation.",
            "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "affects": ["cwb"],
        })
    if ctx["cwb_disability_supplement_eligible"] and not ctx["cwb_basic_eligible"]:
        results.append({
            "id": "cwb_disability_requires_basic_cwb",
            "category": "refundable_credits",
            "status": "review",
            "message": "CWB disability supplement is checked, but basic CWB is not enabled yet.",
            "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "affects": ["cwb_disability_supplement"],
        })
    return results
