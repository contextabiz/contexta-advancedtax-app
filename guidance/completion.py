from typing import Literal, TypedDict

from .progress import SectionProgress
from .screening import ScreeningInputs


class CompletionFlag(TypedDict):
    id: str
    severity: Literal["info", "review", "important"]
    message: str
    where: str
    related_guidance_id: str | None


def build_completion_flags(
    *,
    screening: ScreeningInputs,
    progress: SectionProgress,
    wizard_totals: dict,
    raw_inputs: dict,
    result: dict | None = None,
    readiness_df=None,
    eligibility_decision: dict | None = None,
) -> list[CompletionFlag]:
    flags: list[CompletionFlag] = []

    def add(
        flag_id: str,
        severity: Literal["info", "review", "important"],
        message: str,
        where: str,
        related_guidance_id: str | None,
    ) -> None:
        flags.append(
            {
                "id": flag_id,
                "severity": severity,
                "message": message,
                "where": where,
                "related_guidance_id": related_guidance_id,
            }
        )

    eligibility_decision = eligibility_decision or {
        "rule_results": [],
        "allowed_claims": {},
        "blocked_claims": {},
        "review_flags": [],
    }
    rule_result_by_id = {item["id"]: item for item in eligibility_decision["rule_results"]}

    if (
        screening["has_spouse"]
        and progress["household_reviewed"] == "not_started"
        and "spouse_requires_year_end_status" not in eligibility_decision["review_flags"]
        and "spouse_support_restriction" not in rule_result_by_id
        and "spouse_household_path_reviewed" not in rule_result_by_id
    ):
        add(
            "spouse_not_reviewed",
            "review",
            "A spouse or partner may be relevant here. If you had a spouse or common-law partner at year end and have not reviewed the spouse amount settings yet, you may still have spouse-related credits or benefit eligibility to check.",
            "Section 4 -> Household And Dependants",
            "spouse_amount",
        )
    if "spouse_requires_year_end_status" in eligibility_decision["review_flags"]:
        rule = rule_result_by_id["spouse_requires_year_end_status"]
        add("spouse_requires_year_end_status", "review", rule["message"], rule["where"], "spouse_amount")
    if "spouse_support_restriction" in rule_result_by_id:
        rule = rule_result_by_id["spouse_support_restriction"]
        add("spouse_support_restriction", "important", rule["message"], rule["where"], "spouse_amount")
    if screening["has_dependants"] and progress["household_reviewed"] == "not_started":
        add(
            "dependants_not_reviewed",
            "review",
            "Dependants are indicated, but household-related credits do not look reviewed yet.",
            "Section 4 -> Household And Dependants",
            "household_dependants",
        )
    if "eligible_dependant_other_claimant" in rule_result_by_id:
        rule = rule_result_by_id["eligible_dependant_other_claimant"]
        add("eligible_dependant_other_claimant", "important", rule["message"], rule["where"], "household_dependants")
    if "eligible_dependant_support_review" in eligibility_decision["review_flags"]:
        rule = rule_result_by_id["eligible_dependant_support_review"]
        add("eligible_dependant_support_review", "review", rule["message"], rule["where"], "household_dependants")
    if (
        (screening["paid_tuition"] or screening["paid_student_loan_interest"])
        and progress["carryforward_reviewed"] == "not_started"
        and "training_credit_limit_zero" not in eligibility_decision["review_flags"]
        and "tuition_amount_available" not in rule_result_by_id
        and "tuition_no_available_amount" not in rule_result_by_id
    ):
        add(
            "tuition_not_reviewed",
            "review",
            "Tuition or student-loan signals are showing, but tuition claims or carryforwards do not look reviewed yet.",
            "Section 4 -> Common Credits And Claim Amounts",
            "tuition_and_student",
        )
    if "training_credit_limit_zero" in eligibility_decision["review_flags"]:
        rule = rule_result_by_id["training_credit_limit_zero"]
        add("training_credit_limit_zero", "review", rule["message"], rule["where"], "tuition_and_student")
    if (screening["had_medical_expenses"] or screening["made_donations"]) and progress["section_4_credits"] == "not_started":
        add(
            "common_credits_not_reviewed",
            "review",
            "Medical expenses or donations are indicated, but section 4 credits do not look reviewed yet.",
            "Section 4 -> Common Credits And Claim Amounts",
            "medical_and_donations",
        )
    if (screening["had_work_expenses"] or screening["had_moving_expenses"] or screening["had_child_care_expenses"]) and progress["section_3_deductions"] == "not_started":
        add(
            "deductions_not_reviewed",
            "review",
            "Possible deduction items are indicated, but section 3 does not look reviewed yet.",
            "Section 3 -> Deductions",
            "deductions_review",
        )
    if (screening["had_foreign_income"] or screening["had_investment_income"]) and progress["section_2_income"] == "not_started":
        add(
            "income_not_reviewed",
            "review",
            "Investment or foreign-income signals are showing, but section 2 does not look reviewed yet.",
            "Section 2 -> Income And Investment",
            "foreign_and_investment",
        )
    if screening["had_foreign_income"] and progress["foreign_tax_reviewed"] == "not_started":
        add(
            "foreign_tax_not_reviewed",
            "important",
            "Foreign-income signals are showing, but foreign-tax inputs do not look reviewed yet.",
            "Section 4 -> Foreign Tax And Dividend Credits",
            "foreign_and_investment",
        )
    if screening["low_income_self_assessed"] and progress["refundable_reviewed"] == "not_started":
        add(
            "refundable_not_reviewed",
            "info",
            "Low-income support may matter here, but refundable-credit inputs do not look reviewed yet.",
            "Section 4 -> Refundable Credit Manual Amounts (Advanced)",
            "low_income_refundable",
        )
    if "cwb_not_enabled" in eligibility_decision["review_flags"] and progress["refundable_reviewed"] != "done":
        rule = rule_result_by_id["cwb_not_enabled"]
        add("cwb_not_enabled", "review", rule["message"], rule["where"], "low_income_refundable")
    if "cwb_disability_requires_basic_cwb" in eligibility_decision["review_flags"]:
        rule = rule_result_by_id["cwb_disability_requires_basic_cwb"]
        add("cwb_disability_requires_basic_cwb", "review", rule["message"], rule["where"], "low_income_refundable")
    if result is None and progress["section_1_slips"] == "not_started":
        add(
            "slips_not_started",
            "info",
            "No slip entries are showing yet. Most users should start with slips before anything else.",
            "Section 1A -> Slips And Source Records",
            None,
        )

    severity_rank = {"important": 0, "review": 1, "info": 2}
    deduped_flags: list[CompletionFlag] = []
    seen_messages: set[str] = set()
    for flag in sorted(flags, key=lambda item: severity_rank[item["severity"]]):
        if flag["message"] in seen_messages:
            continue
        seen_messages.add(flag["message"])
        deduped_flags.append(flag)
    return deduped_flags
