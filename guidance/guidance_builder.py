from typing import Literal, TypedDict

from .progress import GuidanceProgress
from .screening import ScreeningInputs


class GuidanceItem(TypedDict):
    id: str
    priority: Literal["likely", "maybe", "easy_to_miss"]
    what: str
    why: str
    where: str
    estimated_here: bool
    confidence: Literal["low", "medium", "high"]


class GuidanceEligibilityDecision(TypedDict):
    rule_results: list[dict]
    allowed_claims: dict[str, bool]
    blocked_claims: dict[str, bool]
    review_flags: list[str]


def build_eligibility_guidance(
    screening: ScreeningInputs,
    eligibility_decision: GuidanceEligibilityDecision | None = None,
    progress: GuidanceProgress | None = None,
) -> list[GuidanceItem]:
    items: list[GuidanceItem] = []
    eligibility_decision = eligibility_decision or {
        "rule_results": [],
        "allowed_claims": {},
        "blocked_claims": {},
        "review_flags": [],
    }
    rule_ids = {item["id"] for item in eligibility_decision["rule_results"]}

    def add_item(item: GuidanceItem) -> None:
        if any(existing["id"] == item["id"] for existing in items):
            return
        items.append(item)

    if screening["has_spouse"] and "spouse_household_path_reviewed" not in rule_ids:
        add_item({
            "id": "spouse_amount",
            "priority": "likely",
            "what": "Check the spouse / common-law partner amount.",
            "why": "This can reduce tax if your spouse or partner had low net income.",
            "where": "Section 4 -> Household And Dependants",
            "estimated_here": True,
            "confidence": "medium",
        })
    if screening["has_dependants"] or screening["wants_household_help"] or any(
        rule_id in rule_ids
        for rule_id in [
            "eligible_dependant_other_claimant",
            "eligible_dependant_support_review",
            "caregiver_other_claimant",
            "caregiver_target_ambiguous",
            "disability_transfer_other_claimant",
            "medical_dependants_shared_review",
        ]
    ):
        add_item({
            "id": "household_dependants",
            "priority": "likely",
            "what": "Review eligible dependant, caregiver, disability transfer, and dependant medical rules.",
            "why": "Household-related claims are easy to miss and can affect both federal and provincial credits.",
            "where": "Section 4 -> Household And Dependants",
            "estimated_here": True,
            "confidence": "medium",
        })
    if (
        (screening["paid_tuition"] or screening["paid_student_loan_interest"])
        and "tuition_no_available_amount" not in rule_ids
    ) or "training_credit_limit_zero" in rule_ids:
        add_item({
            "id": "tuition_and_student",
            "priority": "likely",
            "what": "Check tuition, student loan interest, and any tuition carryforward amounts.",
            "why": "These amounts often create credits now or preserve carryforwards for later years.",
            "where": "Section 4 -> Common Credits And Claim Amounts or Section 4 -> Carryforwards And Transfers",
            "estimated_here": True,
            "confidence": "high",
        })
    if (
        screening["had_medical_expenses"] or screening["made_donations"]
    ) and (
        progress is None
        or progress.get("section_4_credits") != "done"
        or progress.get("carryforward_reviewed") != "done"
    ):
        add_item({
            "id": "medical_and_donations",
            "priority": "likely",
            "what": "Check medical expenses and charitable donations.",
            "why": "Even moderate amounts can create useful non-refundable credits.",
            "where": "Section 4 -> Common Credits And Claim Amounts",
            "estimated_here": True,
            "confidence": "high",
        })
    if (
        screening["had_work_expenses"] or screening["had_moving_expenses"] or screening["had_child_care_expenses"]
    ) and (progress is None or progress.get("section_3_deductions") != "done"):
        add_item({
            "id": "deductions_review",
            "priority": "likely",
            "what": "Review RRSP, FHSA, moving expenses, child care, support payments, and work-related deductions.",
            "why": "Deductions reduce income directly, which can also change other credits and benefits.",
            "where": "Section 3 -> Deductions",
            "estimated_here": True,
            "confidence": "high",
        })
    if (
        screening["had_foreign_income"] or screening["had_investment_income"]
    ) and (
        progress is None
        or progress.get("section_2_income") != "done"
        or progress.get("foreign_tax_reviewed") != "done"
    ):
        add_item({
            "id": "foreign_and_investment",
            "priority": "likely",
            "what": "Review foreign income, dividends, investment income, and foreign tax inputs.",
            "why": "Foreign income, dividends, and investment amounts are easy to misclassify or count twice.",
            "where": "Section 2 -> Income And Investment and Section 4 -> Foreign Tax And Dividend Credits",
            "estimated_here": True,
            "confidence": "medium",
        })
    if (
        screening["low_income_self_assessed"] or "cwb_not_enabled" in rule_ids
    ) and (progress is None or progress.get("refundable_reviewed") != "done" or "cwb_not_enabled" in rule_ids):
        if "cwb_enabled" not in rule_ids:
            add_item({
                "id": "low_income_refundable",
                "priority": "maybe",
                "what": "Check whether Canada Workers Benefit or Medical Expense Supplement may apply.",
                "why": "Lower-income returns often qualify for refundable support that changes the final result.",
                "where": "Section 4 -> Refundable Credit Manual Amounts (Advanced) and Section 6 -> Summary",
                "estimated_here": True,
                "confidence": "medium",
            })
        add_item({
            "id": "gst_hst_credit",
            "priority": "easy_to_miss",
            "what": "Make sure you still file if GST/HST credit may matter to you.",
            "why": "Some benefits are triggered by filing even when no tax is owing.",
            "where": "Outside This Estimator -> CRA benefit eligibility",
            "estimated_here": False,
            "confidence": "medium",
        })
    if screening["province"] == "ON" and screening["paid_rent_or_property_tax"]:
        add_item({
            "id": "ontario_trillium_benefit",
            "priority": "easy_to_miss",
            "what": "Review Ontario Trillium Benefit separately if you paid rent or property tax.",
            "why": "Housing-related Ontario benefits can matter even when the main tax return looks simple.",
            "where": "Outside This Estimator -> Ontario benefit eligibility",
            "estimated_here": False,
            "confidence": "medium",
        })
    elif screening["paid_rent_or_property_tax"] and (progress is None or progress.get("section_4_credits") != "done"):
        add_item({
            "id": "housing_benefits",
            "priority": "maybe",
            "what": "Check whether your housing costs affect province-specific benefits.",
            "why": "Some provinces tie credits or benefits to housing costs, family status, or income level.",
            "where": f"Section 4 -> Province-Specific Credits And Schedules and Outside This Estimator -> {screening['province_name']} benefit guidance",
            "estimated_here": False,
            "confidence": "low",
        })

    if not items and (
        progress is None
        or progress.get("section_3_deductions") != "done"
        or progress.get("section_4_credits") != "done"
        or progress.get("section_5_payments") != "done"
    ):
        add_item({
            "id": "general_follow_up",
            "priority": "maybe",
            "what": "Check for deductions and common credits even if you already entered all your slips.",
            "why": "Many first-time filers miss claimable items simply because they stop after entering slips.",
            "where": "Section 3 -> Deductions and Section 4 -> Common Credits And Claim Amounts",
            "estimated_here": True,
            "confidence": "high",
        })

    return items


def split_guidance_by_priority(
    guidance_items: list[GuidanceItem],
) -> tuple[list[GuidanceItem], list[GuidanceItem], list[GuidanceItem]]:
    likely_items = [item for item in guidance_items if item["priority"] == "likely"]
    maybe_items = [item for item in guidance_items if item["priority"] == "maybe"]
    easy_to_miss_items = [item for item in guidance_items if item["priority"] == "easy_to_miss"]
    return likely_items, maybe_items, easy_to_miss_items
