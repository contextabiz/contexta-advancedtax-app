from .context import build_eligibility_context
from .cwb import evaluate_cwb_eligibility
from .household import evaluate_household_eligibility
from .tuition import evaluate_tuition_eligibility
from .types import EligibilityContext, EligibilityDecision


def evaluate_eligibility_rules(ctx: EligibilityContext) -> EligibilityDecision:
    rule_results = (
        evaluate_household_eligibility(ctx)
        + evaluate_cwb_eligibility(ctx)
        + evaluate_tuition_eligibility(ctx)
    )
    allowed_claims: dict[str, bool] = {}
    blocked_claims: dict[str, bool] = {}
    review_flags: list[str] = []

    for result in rule_results:
        if result["status"] == "allowed":
            for claim_id in result["affects"]:
                allowed_claims[claim_id] = True
        elif result["status"] == "blocked":
            for claim_id in result["affects"]:
                blocked_claims[claim_id] = True
        elif result["status"] == "review":
            review_flags.append(result["id"])

    return {
        "rule_results": rule_results,
        "allowed_claims": allowed_claims,
        "blocked_claims": blocked_claims,
        "review_flags": review_flags,
    }


def build_eligibility_decision(
    *,
    tax_year: int,
    province: str,
    age: float,
    raw_inputs: dict,
    result: dict | None = None,
) -> EligibilityDecision:
    return evaluate_eligibility_rules(
        build_eligibility_context(
            tax_year=tax_year,
            province=province,
            age=age,
            raw_inputs=raw_inputs,
            result=result,
        )
    )
