from typing import TypedDict


class ScreeningInputs(TypedDict):
    has_spouse: bool
    has_dependants: bool
    paid_rent_or_property_tax: bool
    paid_tuition: bool
    paid_student_loan_interest: bool
    had_medical_expenses: bool
    made_donations: bool
    had_moving_expenses: bool
    had_child_care_expenses: bool
    had_work_expenses: bool
    had_foreign_income: bool
    had_investment_income: bool
    low_income_self_assessed: bool
    wants_household_help: bool
    province: str
    province_name: str


def infer_screening_inputs_from_return_data(
    *,
    session_state: dict,
    wizard_totals: dict,
    raw_inputs: dict,
) -> dict[str, bool]:
    def numeric_value(key: str) -> float:
        return float(raw_inputs.get(key, session_state.get(key, 0.0)) or 0.0)

    def bool_value(key: str) -> bool:
        return bool(raw_inputs.get(key, session_state.get(key, False)))

    def has_rows(key: str) -> bool:
        value = session_state.get(key, [])
        return bool(value)

    return {
        "has_spouse": bool_value("spouse_claim_enabled") or bool_value("has_spouse_end_of_year"),
        "has_dependants": (
            bool_value("eligible_dependant_claim_enabled")
            or has_rows("additional_dependants")
            or bool_value("dependant_lived_with_you")
        ),
        "paid_rent_or_property_tax": (
            numeric_value("t776_property_taxes") > 0
            or bool_value("bc_renters_credit_eligible")
            or bool_value("screen_paid_rent_or_property_tax")
        ),
        "paid_tuition": (
            numeric_value("tuition_amount_claim") > 0
            or numeric_value("student_loan_interest") > 0
            or has_rows("t2202_wizard")
            or numeric_value("t2202_tuition_total") > 0
        ),
        "had_medical_expenses": numeric_value("medical_expenses_paid") > 0,
        "made_donations": numeric_value("charitable_donations") > 0 or numeric_value("donations_eligible_total") > 0,
        "had_moving_expenses": numeric_value("moving_expenses") > 0,
        "had_child_care_expenses": numeric_value("child_care_expenses") > 0,
        "had_work_expenses": (
            numeric_value("other_employment_expenses") > 0
            or numeric_value("rrsp_deduction") > 0
            or numeric_value("fhsa_deduction") > 0
            or numeric_value("support_payments_deduction") > 0
        ),
        "had_foreign_income": numeric_value("foreign_income") > 0 or numeric_value("foreign_tax_paid") > 0,
        "had_investment_income": (
            numeric_value("interest_income") > 0
            or numeric_value("eligible_dividends") > 0
            or numeric_value("non_eligible_dividends") > 0
            or bool(wizard_totals.get("t5", 0.0))
            or bool(wizard_totals.get("t3", 0.0))
        ),
    }


def build_screening_inputs(
    *,
    province: str,
    province_name: str,
    session_state: dict,
    wizard_totals: dict,
    raw_inputs: dict,
) -> ScreeningInputs:
    inferred = infer_screening_inputs_from_return_data(
        session_state=session_state,
        wizard_totals=wizard_totals,
        raw_inputs=raw_inputs,
    )

    def bool_value(key: str) -> bool:
        return bool(raw_inputs.get(key, session_state.get(key, False)))

    def numeric_value(key: str) -> float:
        return float(raw_inputs.get(key, session_state.get(key, 0.0)) or 0.0)

    return {
        "has_spouse": bool_value("screen_has_spouse") or inferred["has_spouse"],
        "has_dependants": bool_value("screen_has_dependants") or inferred["has_dependants"],
        "paid_rent_or_property_tax": bool_value("screen_paid_rent_or_property_tax") or inferred["paid_rent_or_property_tax"],
        "paid_tuition": bool_value("screen_paid_tuition_or_student_loan") or inferred["paid_tuition"],
        "paid_student_loan_interest": numeric_value("student_loan_interest") > 0 or bool_value("screen_paid_tuition_or_student_loan"),
        "had_medical_expenses": bool_value("screen_had_medical_or_donations") or inferred["had_medical_expenses"],
        "made_donations": bool_value("screen_had_medical_or_donations") or inferred["made_donations"],
        "had_moving_expenses": bool_value("screen_had_work_or_moving_costs") or inferred["had_moving_expenses"],
        "had_child_care_expenses": bool_value("screen_had_work_or_moving_costs") or inferred["had_child_care_expenses"],
        "had_work_expenses": bool_value("screen_had_work_or_moving_costs") or inferred["had_work_expenses"],
        "had_foreign_income": bool_value("screen_had_foreign_or_investment_income") or inferred["had_foreign_income"],
        "had_investment_income": bool_value("screen_had_foreign_or_investment_income") or inferred["had_investment_income"],
        "low_income_self_assessed": bool_value("screen_low_income"),
        "wants_household_help": bool_value("screen_want_household_review"),
        "province": province,
        "province_name": province_name,
    }
