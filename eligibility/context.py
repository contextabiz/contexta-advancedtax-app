from .types import EligibilityContext


def build_eligibility_context(
    *,
    tax_year: int,
    province: str,
    age: float,
    raw_inputs: dict,
    result: dict | None = None,
) -> EligibilityContext:
    def raw_bool(key: str) -> bool:
        return bool(raw_inputs.get(key, False))

    def raw_float(key: str) -> float:
        return float(raw_inputs.get(key, 0.0) or 0.0)

    result_payload = result or {}
    working_income = (
        float(result_payload.get("line_10100", raw_float("line_10100") or raw_float("estimated_working_income")))
        + float(result_payload.get("line_10400", raw_float("line_10400")))
    )
    adjusted_net_income = float(
        result_payload.get(
            "adjusted_net_income_for_lift",
            result_payload.get(
                "net_income",
                raw_float("adjusted_net_income_for_lift") or raw_float("estimated_adjusted_net_income_for_cwb") or raw_float("estimated_net_income"),
            ),
        )
    )
    spouse_adjusted_net_income = float(
        result_payload.get(
            "spouse_adjusted_net_income_for_lift",
            raw_float("spouse_adjusted_net_income_for_lift") or raw_float("estimated_spouse_adjusted_net_income_for_cwb") or raw_float("spouse_net_income"),
        )
    )

    return {
        "tax_year": tax_year,
        "province": province,
        "age": age,
        "has_spouse": raw_bool("screen_has_spouse") or raw_bool("has_spouse_end_of_year") or raw_bool("spouse_claim_enabled"),
        "spouse_net_income": raw_float("spouse_net_income"),
        "spouse_infirm": raw_bool("spouse_infirm"),
        "has_spouse_end_of_year": raw_bool("has_spouse_end_of_year"),
        "separated_in_year": raw_bool("separated_in_year"),
        "support_payments_to_spouse": raw_bool("support_payments_to_spouse"),
        "eligible_dependant_claim_enabled": raw_bool("eligible_dependant_claim_enabled"),
        "eligible_dependant_net_income": raw_float("eligible_dependant_net_income"),
        "eligible_dependant_infirm": raw_bool("eligible_dependant_infirm"),
        "dependant_lived_with_you": raw_bool("dependant_lived_with_you"),
        "dependant_relationship": str(raw_inputs.get("dependant_relationship", "")),
        "dependant_category": str(raw_inputs.get("dependant_category", "")),
        "paid_child_support_for_dependant": raw_bool("paid_child_support_for_dependant"),
        "shared_custody_claim_agreement": raw_bool("shared_custody_claim_agreement"),
        "another_household_member_claims_dependant": raw_bool("another_household_member_claims_dependant"),
        "another_household_member_claims_caregiver": raw_bool("another_household_member_claims_caregiver"),
        "another_household_member_claims_disability_transfer": raw_bool("another_household_member_claims_disability_transfer"),
        "medical_dependant_claim_shared": raw_bool("medical_dependant_claim_shared"),
        "caregiver_claim_amount": raw_float("caregiver_claim_amount"),
        "caregiver_claim_target": str(raw_inputs.get("caregiver_claim_target", "")),
        "ontario_disability_transfer": raw_float("ontario_disability_transfer"),
        "disability_transfer_source": str(raw_inputs.get("disability_transfer_source", "")),
        "spouse_disability_transfer_available": raw_bool("spouse_disability_transfer_available"),
        "spouse_disability_transfer_available_amount": raw_float("spouse_disability_transfer_available_amount"),
        "dependant_disability_transfer_available": raw_bool("dependant_disability_transfer_available"),
        "dependant_disability_transfer_available_amount": raw_float("dependant_disability_transfer_available_amount"),
        "ontario_medical_dependants": raw_float("ontario_medical_dependants"),
        "cwb_basic_eligible": raw_bool("cwb_basic_eligible"),
        "cwb_disability_supplement_eligible": raw_bool("cwb_disability_supplement_eligible"),
        "spouse_cwb_disability_supplement_eligible": raw_bool("spouse_cwb_disability_supplement_eligible"),
        "working_income": working_income,
        "adjusted_net_income": adjusted_net_income,
        "spouse_adjusted_net_income": spouse_adjusted_net_income,
        "cwb_preview_amount": float(result_payload.get("canada_workers_benefit_preview", raw_float("canada_workers_benefit_preview"))),
        "cwb_no_basic_amount_above": float(
            result_payload.get(
                "canada_workers_benefit_preview_no_basic_amount_above",
                result_payload.get("canada_workers_benefit_no_basic_amount_above", raw_float("canada_workers_benefit_no_basic_amount_above")),
            )
        ),
        "tuition_amount_available": raw_float("schedule11_current_year_tuition_available"),
        "tuition_transfer_from_spouse": raw_float("tuition_transfer_from_spouse"),
        "tuition_carryforward_available": raw_float("schedule11_carryforward_available"),
        "canada_training_credit_limit_available": raw_float("canada_training_credit_limit_available"),
    }
