from typing import Literal, TypedDict


class GuidanceProgress(TypedDict, total=False):
    section_3_deductions: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_4_credits: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_5_payments: Literal["not_started", "in_progress", "done", "not_applicable"]
    foreign_tax_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    carryforward_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    refundable_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_2_income: Literal["not_started", "in_progress", "done", "not_applicable"]


class SectionProgress(TypedDict):
    section_1_slips: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_2_income: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_3_deductions: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_4_credits: Literal["not_started", "in_progress", "done", "not_applicable"]
    section_5_payments: Literal["not_started", "in_progress", "done", "not_applicable"]
    household_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    foreign_tax_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    carryforward_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    refundable_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]
    summary_reviewed: Literal["not_started", "in_progress", "done", "not_applicable"]


def build_section_progress(
    *,
    session_state: dict,
    wizard_totals: dict,
    raw_inputs: dict,
    result: dict | None = None,
    eligibility_decision: dict | None = None,
) -> SectionProgress:
    def numeric_value(key: str) -> float:
        return float(raw_inputs.get(key, session_state.get(key, 0.0)) or 0.0)

    def bool_value(key: str) -> bool:
        return bool(raw_inputs.get(key, session_state.get(key, False)))

    def has_rows(key: str) -> bool:
        return bool(session_state.get(key, []))

    def wizard_has_nonzero(key: str, fields: list[str]) -> bool:
        rows = session_state.get(key, [])
        if not rows:
            return False
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in fields:
                try:
                    if float(row.get(field, 0.0) or 0.0) > 0:
                        return True
                except (TypeError, ValueError):
                    continue
        return False

    eligibility_decision = eligibility_decision or {
        "rule_results": [],
        "allowed_claims": {},
        "blocked_claims": {},
        "review_flags": [],
    }
    household_rules = [item for item in eligibility_decision["rule_results"] if item["category"] == "household"]
    household_rule_ids = {item["id"] for item in household_rules}
    household_has_review_or_block = any(item["status"] in {"review", "blocked"} for item in household_rules)
    tuition_rules = [item for item in eligibility_decision["rule_results"] if item["category"] == "tuition"]
    tuition_rule_ids = {item["id"] for item in tuition_rules}
    refundable_rules = [item for item in eligibility_decision["rule_results"] if item["category"] == "refundable_credits"]
    refundable_rule_ids = {item["id"] for item in refundable_rules}
    foreign_slip_started = (
        wizard_has_nonzero("t5_wizard", ["box15_foreign_income", "box16_foreign_tax_paid"])
        or wizard_has_nonzero("t3_wizard", ["box25_foreign_income", "box34_foreign_tax_paid"])
        or wizard_has_nonzero("t4ps_wizard", ["box37_foreign_non_business_income"])
    )
    foreign_worksheet_started = any(
        numeric_value(key) > 0
        for key in [
            "t2209_non_business_tax_paid",
            "t2209_net_foreign_non_business_income",
            "t2209_net_income_override",
            "t2209_basic_federal_tax_override",
            "t2036_provincial_tax_otherwise_payable_override",
        ]
    )
    foreign_credit_claimed = bool(
        result is not None
        and (
            float(result.get("federal_foreign_tax_credit", 0.0)) > 0
            or float(result.get("provincial_foreign_tax_credit", 0.0)) > 0
            or float(result.get("t2209_non_business_tax_paid", 0.0)) > 0
            or float(result.get("t2209_net_foreign_non_business_income", 0.0)) > 0
        )
    )

    slips_started = any(has_rows(key) for key in ["t4_wizard", "t4a_wizard", "t5_wizard", "t3_wizard", "t4ps_wizard", "t2202_wizard"])
    slips_done = slips_started
    section_2_manual_started = any(
        numeric_value(key) > 0
        for key in [
            "employment_income",
            "pension_income",
            "rrsp_rrif_income",
            "other_income",
            "interest_income",
            "eligible_dividends",
            "non_eligible_dividends",
            "foreign_income",
            "foreign_tax_paid",
        ]
    )
    section_2_slip_started = (
        wizard_has_nonzero("t5_wizard", ["box13_interest", "box15_foreign_income", "box25_eligible_dividends_taxable", "box11_non_eligible_dividends_taxable"])
        or wizard_has_nonzero("t3_wizard", ["box21_capital_gains", "box26_other_income", "box25_foreign_income", "box50_eligible_dividends_taxable", "box32_non_eligible_dividends_taxable"])
        or wizard_has_nonzero("t4ps_wizard", ["box25_non_eligible_dividends_taxable", "box31_eligible_dividends_taxable", "box34_capital_gains_or_losses", "box35_other_employment_income", "box37_foreign_non_business_income"])
    )
    section_2_started = section_2_manual_started or section_2_slip_started
    section_2_done = section_2_started and (
        numeric_value("employment_income") > 0
        or numeric_value("pension_income") > 0
        or numeric_value("other_income") > 0
        or numeric_value("interest_income") > 0
        or numeric_value("eligible_dividends") > 0
        or numeric_value("non_eligible_dividends") > 0
        or section_2_slip_started
    )
    section_3_started = any(
        numeric_value(key) > 0
        for key in [
            "rrsp_deduction",
            "fhsa_deduction",
            "child_care_expenses",
            "moving_expenses",
            "support_payments_deduction",
            "carrying_charges",
            "other_employment_expenses",
            "other_deductions",
            "net_capital_loss_carryforward",
            "other_loss_carryforward",
        ]
    )
    section_3_done = section_3_started and (
        numeric_value("rrsp_deduction") > 0
        or numeric_value("fhsa_deduction") > 0
        or numeric_value("child_care_expenses") > 0
        or numeric_value("moving_expenses") > 0
        or numeric_value("other_employment_expenses") > 0
    )
    section_4_started = any(
        bool_value(key)
        for key in [
            "spouse_claim_enabled",
            "eligible_dependant_claim_enabled",
            "screen_has_spouse",
            "screen_has_dependants",
            "screen_want_household_review",
        ]
    ) or any(
        numeric_value(key) > 0
        for key in [
            "spouse_amount_claim",
            "student_loan_interest",
            "medical_expenses_paid",
            "charitable_donations",
            "tuition_amount_claim",
            "foreign_income",
            "foreign_tax_paid",
            "canada_workers_benefit",
            "medical_expense_supplement",
        ]
    ) or has_rows("additional_dependants") or foreign_slip_started or foreign_worksheet_started or foreign_credit_claimed
    section_4_done = section_4_started and (
        numeric_value("student_loan_interest") > 0
        or numeric_value("medical_expenses_paid") > 0
        or numeric_value("charitable_donations") > 0
        or numeric_value("spouse_amount_claim") > 0
        or numeric_value("eligible_dependant_claim") > 0
        or numeric_value("foreign_income") > 0
        or numeric_value("foreign_tax_paid") > 0
        or has_rows("additional_dependants")
        or bool_value("spouse_claim_enabled")
        or bool_value("eligible_dependant_claim_enabled")
        or foreign_worksheet_started
        or foreign_credit_claimed
    )
    section_5_started = any(
        numeric_value(key) > 0
        for key in [
            "income_tax_withheld",
            "cpp_withheld",
            "ei_withheld",
            "installments_paid",
            "other_payments",
        ]
    )
    section_5_done = section_5_started and (
        numeric_value("income_tax_withheld") > 0
        or numeric_value("installments_paid") > 0
        or numeric_value("other_payments") > 0
    )
    household_started = (
        bool_value("spouse_claim_enabled")
        or bool_value("eligible_dependant_claim_enabled")
        or numeric_value("spouse_amount_claim") > 0
        or numeric_value("eligible_dependant_claim") > 0
        or numeric_value("spouse_net_income") > 0
        or has_rows("additional_dependants")
        or bool(household_rules)
    )
    household_done = household_started and (
        not household_has_review_or_block
        and (
            numeric_value("spouse_net_income") > 0
            or numeric_value("spouse_amount_claim") > 0
            or numeric_value("eligible_dependant_claim") > 0
            or has_rows("additional_dependants")
            or "spouse_household_path_reviewed" in household_rule_ids
        )
    )
    foreign_started = (
        any(
            numeric_value(key) > 0
            for key in [
                "foreign_income",
                "foreign_tax_paid",
                "t2209_non_business_tax_paid",
                "t2209_net_foreign_non_business_income",
                "t2209_net_income_override",
                "t2209_basic_federal_tax_override",
                "t2036_provincial_tax_otherwise_payable_override",
            ]
        )
        or foreign_slip_started
        or foreign_credit_claimed
    )
    foreign_done = foreign_started and (
        numeric_value("foreign_income") > 0
        or numeric_value("foreign_tax_paid") > 0
        or foreign_worksheet_started
        or foreign_credit_claimed
    )
    carryforward_started = (
        has_rows("tuition_carryforwards")
        or has_rows("donation_carryforwards")
        or has_rows("provincial_credit_lines")
        or bool(tuition_rules)
    )
    carryforward_done = carryforward_started and (
        "tuition_amount_available" in tuition_rule_ids
        or "tuition_no_available_amount" in tuition_rule_ids
        or has_rows("tuition_carryforwards")
        or has_rows("donation_carryforwards")
        or has_rows("provincial_credit_lines")
    )
    refundable_started = any(
        numeric_value(key) > 0
        for key in [
            "canada_workers_benefit",
            "canada_training_credit",
            "medical_expense_supplement",
            "other_federal_refundable_credits",
            "manual_provincial_refundable_credits",
            "refundable_credits",
        ]
    ) or bool_value("cwb_basic_eligible") or bool(refundable_rules)
    refundable_done = refundable_started and (
        numeric_value("canada_workers_benefit") > 0
        or numeric_value("canada_training_credit") > 0
        or numeric_value("medical_expense_supplement") > 0
        or numeric_value("other_federal_refundable_credits") > 0
        or numeric_value("manual_provincial_refundable_credits") > 0
        or bool_value("cwb_basic_eligible")
        or "cwb_enabled" in refundable_rule_ids
        or "cwb_out_of_range_or_not_enabled" in refundable_rule_ids
    )
    section_4_done = section_4_done or household_done or foreign_done or carryforward_done or refundable_done

    def status(started: bool, done: bool = False) -> Literal["not_started", "in_progress", "done", "not_applicable"]:
        if done:
            return "done"
        return "in_progress" if started else "not_started"

    return {
        "section_1_slips": status(slips_started, slips_done),
        "section_2_income": status(section_2_started, section_2_done),
        "section_3_deductions": status(section_3_started, section_3_done),
        "section_4_credits": status(section_4_started, section_4_done),
        "section_5_payments": status(section_5_started, section_5_done),
        "household_reviewed": status(household_started, household_done),
        "foreign_tax_reviewed": status(foreign_started, foreign_done),
        "carryforward_reviewed": status(carryforward_started, carryforward_done),
        "refundable_reviewed": status(refundable_started, refundable_done),
        "summary_reviewed": "done" if result is not None else "not_started",
    }
