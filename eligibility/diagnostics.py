from diagnostics.types import DiagnosticItem

from .types import EligibilityDecision


def build_rules_diagnostics(
    *,
    context: dict[str, float | int | bool],
    eligibility_decision: EligibilityDecision,
) -> list[DiagnosticItem]:
    checks: list[DiagnosticItem] = []
    rule_result_by_id = {item["id"]: item for item in eligibility_decision["rule_results"]}

    def add(severity: str, category: str, message: str) -> None:
        checks.append((severity, category, message))

    if "spouse_requires_year_end_status" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["spouse_requires_year_end_status"]["message"])
    if "spouse_support_restriction" in rule_result_by_id:
        add("High", "Household", rule_result_by_id["spouse_support_restriction"]["message"])
    if "spouse_household_path_reviewed" in rule_result_by_id and not bool(context.get("separated_in_year", False)):
        add("Info", "Household", "Spouse amount settings have been reviewed. If the final spouse-related amount still looks off, check spouse net income and any support or separation details.")
    if "eligible_dependant_support_review" in eligibility_decision["review_flags"]:
        add("High", "Household", rule_result_by_id["eligible_dependant_support_review"]["message"])
    if "eligible_dependant_other_claimant" in rule_result_by_id:
        add("High", "Household", rule_result_by_id["eligible_dependant_other_claimant"]["message"])
    if "caregiver_other_claimant" in rule_result_by_id:
        add("High", "Household", rule_result_by_id["caregiver_other_claimant"]["message"])
    if "caregiver_target_ambiguous" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["caregiver_target_ambiguous"]["message"])
    if "caregiver_dependant_category_review" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["caregiver_dependant_category_review"]["message"])
    if "caregiver_supporting_context_missing" in eligibility_decision["review_flags"]:
        add("Info", "Household", rule_result_by_id["caregiver_supporting_context_missing"]["message"])
    if "disability_transfer_other_claimant" in rule_result_by_id:
        add("High", "Household", rule_result_by_id["disability_transfer_other_claimant"]["message"])
    if "disability_transfer_source_ambiguous" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["disability_transfer_source_ambiguous"]["message"])
    if "spouse_disability_transfer_unavailable" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["spouse_disability_transfer_unavailable"]["message"])
    if "dependant_disability_transfer_unavailable" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["dependant_disability_transfer_unavailable"]["message"])
    if "spouse_disability_transfer_exceeds_available" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["spouse_disability_transfer_exceeds_available"]["message"])
    if "dependant_disability_transfer_exceeds_available" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["dependant_disability_transfer_exceeds_available"]["message"])
    if "disability_transfer_no_source_context" in eligibility_decision["review_flags"]:
        add("Info", "Household", rule_result_by_id["disability_transfer_no_source_context"]["message"])
    if "medical_dependants_shared_review" in eligibility_decision["review_flags"]:
        add("Warning", "Household", rule_result_by_id["medical_dependants_shared_review"]["message"])
    if "medical_dependants_minor_child_review" in eligibility_decision["review_flags"]:
        add("Info", "Household", rule_result_by_id["medical_dependants_minor_child_review"]["message"])

    if (
        "cwb_enabled" in rule_result_by_id
        and float(context.get("canada_workers_benefit_auto", 0.0) or 0.0) == 0
        and float(context.get("canada_workers_benefit_manual", 0.0) or 0.0) == 0
    ):
        add("Info", "Refundable credits", "CWB has already been flagged for review. If the amount still looks off, check working income, family-income range, and any Schedule 6 restrictions.")
    if "cwb_disability_requires_basic_cwb" in eligibility_decision["review_flags"]:
        add("Info", "Refundable credits", rule_result_by_id["cwb_disability_requires_basic_cwb"]["message"])

    return checks


def build_postcalc_rules_diagnostics(
    *,
    result: dict[str, float],
) -> list[DiagnosticItem]:
    checks: list[DiagnosticItem] = []

    def add(severity: str, category: str, message: str) -> None:
        checks.append((severity, category, message))

    cwb_manual = result.get("canada_workers_benefit_manual", 0.0)
    cwb_auto = result.get("canada_workers_benefit_auto", 0.0)
    cwb_used = result.get("canada_workers_benefit", 0.0)
    if cwb_manual > 0 and abs(cwb_manual - cwb_auto) > 100.0:
        add("Info", "Refundable credits", "Manual Canada Workers Benefit override differs materially from the app's auto estimate. Review the CWB worksheet if you entered the amount manually.")
    if cwb_used == 0 and cwb_auto > 0:
        add("Info", "Refundable credits", "The app calculated a positive Canada Workers Benefit estimate, but it was not used. Review whether a manual override or another input suppressed it.")
    if result.get("cwb_disability_supplement_auto", 0.0) > 0:
        add("Info", "Refundable credits", "The final Canada Workers Benefit includes a disability supplement estimate.")
    if result.get("cwb_disability_supplement_eligible", 0.0) > 0 and cwb_manual > 0:
        add("Info", "Refundable credits", "A manual Canada Workers Benefit override is being used while CWB disability supplement eligibility is checked. Review whether the manual total already includes the supplement.")

    training_manual = result.get("canada_training_credit_manual", 0.0)
    training_auto = result.get("canada_training_credit_auto", 0.0)
    training_limit = result.get("canada_training_credit_limit_available", 0.0)
    if training_manual > 0 and training_limit > 0 and training_manual > training_limit:
        add("Warning", "Refundable credits", "Manual Canada Training Credit exceeds the training credit limit available entered. The app used the manual override, so review the Schedule 11 / training-credit worksheet.")
    if training_auto == 0 and training_limit > 0 and result.get("schedule11_current_year_claim_used", 0.0) == 0:
        add("Info", "Refundable credits", "A training credit limit is available, but no current-year tuition/training claim was used. The automatic Canada Training Credit therefore stayed at zero.")

    medical_manual = result.get("medical_expense_supplement_manual", 0.0)
    medical_auto = result.get("medical_expense_supplement_auto", 0.0)
    if medical_manual > 0 and abs(medical_manual - medical_auto) > 100.0:
        add("Info", "Refundable credits", "Manual Medical Expense Supplement override differs materially from the app's auto estimate. Review the supplement worksheet if you entered it manually.")
    if medical_auto == 0 and result.get("medical_expense_supplement", 0.0) == 0 and result.get("federal_medical_claim", 0.0) > 0:
        add("Info", "Refundable credits", "A federal medical claim exists, but no Medical Expense Supplement was produced. This can be correct if income thresholds are not met.")

    cpp_refund = result.get("cpp_overpayment_refund", 0.0)
    ei_refund = result.get("ei_overpayment_refund", 0.0)
    if cpp_refund > 0:
        add("Info", "Payroll refund", "CPP withheld on slips is above the app's employee CPP estimate, so a CPP overpayment refund estimate was included.")
    if ei_refund > 0:
        add("Info", "Payroll refund", "EI withheld on slips is above the app's EI estimate, so an EI overpayment refund estimate was included.")

    return checks
