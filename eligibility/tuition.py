from .types import EligibilityContext, EligibilityRuleResult


def evaluate_tuition_eligibility(ctx: EligibilityContext) -> list[EligibilityRuleResult]:
    results: list[EligibilityRuleResult] = []

    if ctx["tuition_amount_available"] <= 0 and ctx["tuition_carryforward_available"] <= 0:
        results.append({
            "id": "tuition_no_available_amount",
            "category": "tuition",
            "status": "blocked",
            "message": "No current-year tuition or tuition carryforward amount is currently available.",
            "where": "Section 4 -> Common Credits And Claim Amounts",
            "affects": ["tuition_claim"],
        })
    if ctx["canada_training_credit_limit_available"] <= 0 and ctx["tuition_amount_available"] > 0:
        results.append({
            "id": "training_credit_limit_zero",
            "category": "tuition",
            "status": "review",
            "message": "Current-year tuition is present, but no Canada Training Credit limit is showing.",
            "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "affects": ["canada_training_credit"],
        })
    if ctx["tuition_amount_available"] > 0 or ctx["tuition_carryforward_available"] > 0:
        results.append({
            "id": "tuition_amount_available",
            "category": "tuition",
            "status": "allowed",
            "message": "Tuition-related amounts are available for review or claim.",
            "where": "Section 4 -> Common Credits And Claim Amounts",
            "affects": ["tuition_claim", "tuition_carryforward"],
        })
    return results
