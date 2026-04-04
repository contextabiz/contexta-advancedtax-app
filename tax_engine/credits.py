from __future__ import annotations

from typing import Any

from .constants import (
    BC_DONATION_THRESHOLDS,
    BC_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    BC_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    BC_REFUNDABLE_CREDIT_CONFIG,
    BC_TAX_REDUCTION_CONFIG,
    CWB_CONFIG,
    CWB_DISABILITY_SUPPLEMENT_CONFIG,
    MEDICAL_EXPENSE_SUPPLEMENT_CONFIG,
    NB_LOW_INCOME_REDUCTION,
    NL_LOW_INCOME_REDUCTION,
    NS_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    ONTARIO_REFUNDABLE_CREDIT_CONFIG,
    ONTARIO_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    ONTARIO_LIFT_CONFIG,
    ONTARIO_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    PE_LOW_INCOME_REDUCTION,
)
from .utils import value


def calculate_donation_credit(donation_amount: float, base_rate: float) -> float:
    if donation_amount <= 0:
        return 0.0
    first_portion = min(200.0, donation_amount)
    remaining = max(0.0, donation_amount - 200.0)
    return first_portion * base_rate + remaining * 0.29


def calculate_age_amount(age: float, net_income: float, config: dict[str, float]) -> float:
    if age < 65:
        return 0.0
    base_amount = config["base_amount"]
    threshold = config["income_threshold"]
    phaseout_end = config["phaseout_end"]
    if net_income <= threshold:
        return base_amount
    if net_income >= phaseout_end:
        return 0.0
    reduction = ((net_income - threshold) / (phaseout_end - threshold)) * base_amount
    return max(0.0, base_amount - reduction)


def calculate_medical_claim(total_medical_expenses: float, net_income: float, threshold_cap: float) -> float:
    threshold = min(threshold_cap, net_income * 0.03)
    return max(0.0, total_medical_expenses - threshold)


def calculate_canada_workers_benefit(
    tax_year: int,
    working_income: float,
    adjusted_net_income: float,
    spouse_adjusted_net_income: float,
    has_spouse: bool,
) -> dict[str, float]:
    config = CWB_CONFIG.get(tax_year)
    if not config:
        return {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    bucket = config["family"] if has_spouse else config["single"]
    working_income_excess = max(0.0, working_income - bucket["excluded_working_income"])
    base_credit = min(bucket["max_credit"], working_income_excess * bucket["rate"])
    family_income = adjusted_net_income + (spouse_adjusted_net_income if has_spouse else 0.0)
    phaseout_base = max(0.0, family_income - bucket["phaseout_threshold"])
    phaseout = phaseout_base * bucket["phaseout_rate"]
    return {
        "base_credit": base_credit,
        "phaseout": phaseout,
        "credit": max(0.0, base_credit - phaseout),
    }


def calculate_cwb_disability_supplement(
    tax_year: int,
    adjusted_net_income: float,
    spouse_adjusted_net_income: float,
    has_spouse: bool,
    is_disabled: bool,
    spouse_is_disabled: bool,
) -> dict[str, float]:
    if not is_disabled:
        return {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    config = CWB_DISABILITY_SUPPLEMENT_CONFIG.get(tax_year)
    if not config:
        return {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    if not has_spouse:
        bucket = config["single"]
        family_income = adjusted_net_income
    elif spouse_is_disabled:
        bucket = config["family_both_disabled"]
        family_income = adjusted_net_income + spouse_adjusted_net_income
    else:
        bucket = config["family_one_disabled"]
        family_income = adjusted_net_income + spouse_adjusted_net_income
    base_credit = bucket["max_credit"]
    if family_income <= bucket["phaseout_threshold"]:
        phaseout = 0.0
    elif family_income >= bucket["phaseout_end"]:
        phaseout = bucket["max_credit"]
    else:
        phaseout = ((family_income - bucket["phaseout_threshold"]) / (bucket["phaseout_end"] - bucket["phaseout_threshold"])) * bucket["max_credit"]
    return {
        "base_credit": base_credit,
        "phaseout": phaseout,
        "credit": max(0.0, base_credit - phaseout),
    }


def calculate_medical_expense_supplement(
    tax_year: int,
    employment_income: float,
    net_income: float,
    medical_claim: float,
) -> dict[str, float]:
    config = MEDICAL_EXPENSE_SUPPLEMENT_CONFIG.get(tax_year)
    if not config:
        return {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    if employment_income < config["employment_income_threshold"] or medical_claim <= 0:
        return {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    base_credit = min(config["max_credit"], medical_claim * config["rate"])
    phaseout_base = max(0.0, net_income - config["phaseout_threshold"])
    phaseout = phaseout_base * config["phaseout_rate"]
    return {
        "base_credit": base_credit,
        "phaseout": phaseout,
        "credit": max(0.0, base_credit - phaseout),
    }


def calculate_payroll_overpayment_refunds(
    cpp_withheld: float,
    ei_withheld: float,
    expected_cpp: float,
    expected_ei: float,
) -> dict[str, float]:
    cpp_overpayment = max(0.0, cpp_withheld - expected_cpp)
    ei_overpayment = max(0.0, ei_withheld - expected_ei)
    return {
        "cpp_overpayment": cpp_overpayment,
        "ei_overpayment": ei_overpayment,
        "total_refund": cpp_overpayment + ei_overpayment,
    }


def calculate_ontario_fertility_credit(tax_year: int, eligible_expenses: float) -> float:
    config = ONTARIO_REFUNDABLE_CREDIT_CONFIG.get(tax_year)
    if not config:
        return 0.0
    return min(max(0.0, eligible_expenses), config["fertility_expense_cap"]) * config["fertility_rate"]


def calculate_ontario_seniors_transit_credit(tax_year: int, eligible_expenses: float, age: float) -> float:
    config = ONTARIO_REFUNDABLE_CREDIT_CONFIG.get(tax_year)
    if not config or age < 65:
        return 0.0
    return min(max(0.0, eligible_expenses), config["seniors_transit_expense_cap"]) * config["seniors_transit_rate"]


def calculate_bc_renters_credit(
    tax_year: int,
    adjusted_family_net_income: float,
    eligible: bool,
) -> dict[str, float]:
    config = BC_REFUNDABLE_CREDIT_CONFIG.get(tax_year)
    if not config or not eligible:
        return {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    base_credit = config["renter_credit"]
    phaseout_base = max(0.0, adjusted_family_net_income - config["renter_threshold"])
    phaseout = min(base_credit, phaseout_base * config["renter_phaseout_rate"])
    return {"base_credit": base_credit, "phaseout": phaseout, "credit": max(0.0, base_credit - phaseout)}


def calculate_bc_home_renovation_credit(
    tax_year: int,
    eligible_expenses: float,
    eligible: bool,
) -> float:
    config = BC_REFUNDABLE_CREDIT_CONFIG.get(tax_year)
    if not config or not eligible:
        return 0.0
    return min(max(0.0, eligible_expenses), config["home_reno_expense_cap"]) * config["home_reno_rate"]


def calculate_sk_fertility_credit(eligible_expenses: float) -> float:
    return min(max(0.0, eligible_expenses), 20000.0) * 0.50


def calculate_pe_volunteer_credit(eligible: bool) -> float:
    return 1000.0 if eligible else 0.0


def calculate_lift_credit(
    tax_year: int,
    employment_income_line_10100: float,
    self_employment_income_line_10400: float,
    adjusted_net_income: float,
    spouse_adjusted_net_income: float,
    has_spouse: bool,
) -> dict[str, float]:
    config = ONTARIO_LIFT_CONFIG.get(tax_year)
    if not config:
        return {"max_credit": 0.0, "credit": 0.0}
    max_credit = min(
        (employment_income_line_10100 + self_employment_income_line_10400) * config["employment_rate"],
        config["max_credit"],
    )
    if not has_spouse:
        reduction_base = max(0.0, adjusted_net_income - config["single_threshold"])
    else:
        individual_excess = max(0.0, adjusted_net_income - config["single_threshold"])
        family_excess = max(0.0, adjusted_net_income + spouse_adjusted_net_income - config["family_threshold"])
        reduction_base = max(individual_excess, family_excess)
    reduction = reduction_base * config["phaseout_rate"]
    return {"max_credit": max_credit, "credit": max(0.0, max_credit - reduction), "reduction_base": reduction_base}


def calculate_bc_tax_reduction(tax_year: int, net_income: float) -> dict[str, float]:
    config = BC_TAX_REDUCTION_CONFIG.get(tax_year)
    if not config:
        return {"max_credit": 0.0, "credit": 0.0, "reduction_base": 0.0}
    reduction_base = max(0.0, net_income - config["net_income_threshold"])
    reduction = reduction_base * config["reduction_rate"]
    return {"max_credit": config["base_amount"], "credit": max(0.0, config["base_amount"] - reduction), "reduction_base": reduction_base}


def calculate_spouse_amount(bpa: float, spouse_net_income: float, infirmity: bool) -> float:
    caregiver_addition = 2687.0 if infirmity else 0.0
    return max(0.0, bpa + caregiver_addition - spouse_net_income)


def calculate_eligible_dependant_amount(bpa: float, dependant_net_income: float, infirmity: bool) -> float:
    caregiver_addition = 2687.0 if infirmity else 0.0
    return max(0.0, bpa + caregiver_addition - dependant_net_income)


def evaluate_household_claims(data: dict[str, Any], bpa: float) -> dict[str, Any]:
    spouse_enabled = bool(data.get("spouse_claim_enabled", False))
    has_spouse_end_of_year = bool(data.get("has_spouse_end_of_year", False))
    separated_in_year = bool(data.get("separated_in_year", False))
    spouse_infirm = bool(data.get("spouse_infirm", False))
    spouse_net_income = value(data, "spouse_net_income")
    support_payments_to_spouse = bool(data.get("support_payments_to_spouse", False))

    eligible_enabled = bool(data.get("eligible_dependant_claim_enabled", False))
    eligible_infirm = bool(data.get("eligible_dependant_infirm", False))
    eligible_dependant_net_income = value(data, "eligible_dependant_net_income")
    dependant_lived_with_you = bool(data.get("dependant_lived_with_you", False))
    dependant_relationship = str(data.get("dependant_relationship", "Child"))
    dependant_category = str(data.get("dependant_category", "Minor child"))
    paid_child_support_for_dependant = bool(data.get("paid_child_support_for_dependant", False))
    shared_custody_claim_agreement = bool(data.get("shared_custody_claim_agreement", False))
    another_household_member_claims_dependant = bool(data.get("another_household_member_claims_dependant", False))
    another_household_member_claims_caregiver = bool(data.get("another_household_member_claims_caregiver", False))
    another_household_member_claims_disability_transfer = bool(data.get("another_household_member_claims_disability_transfer", False))
    medical_dependant_claim_shared = bool(data.get("medical_dependant_claim_shared", False))
    spouse_disability_transfer_available = bool(data.get("spouse_disability_transfer_available", False))
    dependant_disability_transfer_available = bool(data.get("dependant_disability_transfer_available", False))
    spouse_disability_transfer_available_amount = value(data, "spouse_disability_transfer_available_amount")
    dependant_disability_transfer_available_amount = value(data, "dependant_disability_transfer_available_amount")
    additional_dependant_caregiver_claim_total = value(data, "additional_dependant_caregiver_claim_total")
    additional_dependant_disability_transfer_available_total = value(data, "additional_dependant_disability_transfer_available_total")
    additional_dependant_medical_claim_total = value(data, "additional_dependant_medical_claim_total")
    caregiver_claim_target = str(data.get("caregiver_claim_target", "Auto"))
    disability_transfer_source = str(data.get("disability_transfer_source", "Auto"))

    qualifies_as_dependant_relative = dependant_relationship in {"Child", "Parent/Grandparent", "Other relative"}
    qualifies_for_caregiver_relationship = dependant_relationship in {"Child", "Parent/Grandparent", "Other relative"}
    qualifies_for_medical_dependant_relationship = dependant_relationship in {"Child", "Parent/Grandparent", "Other relative"}
    is_minor_child_dependant = dependant_category == "Minor child"
    is_adult_dependant_category = dependant_category in {"Adult child", "Parent/Grandparent", "Other adult relative"}
    spouse_disability_transfer_available_effective = spouse_disability_transfer_available_amount
    dependant_disability_transfer_available_effective = dependant_disability_transfer_available_amount
    if spouse_disability_transfer_available and spouse_disability_transfer_available_effective == 0.0:
        spouse_disability_transfer_available_effective = value(data, "ontario_disability_transfer")
    if dependant_disability_transfer_available and dependant_disability_transfer_available_effective == 0.0:
        dependant_disability_transfer_available_effective = value(data, "ontario_disability_transfer")
    dependant_disability_transfer_available_effective += additional_dependant_disability_transfer_available_total

    spouse_allowed = False
    spouse_reason = "Not requested."
    spouse_auto_amount = 0.0
    if spouse_enabled:
        if not has_spouse_end_of_year:
            spouse_reason = "Spouse claim was selected, but 'Had Spouse at Year End' is not checked."
        elif support_payments_to_spouse:
            spouse_reason = "Spouse claim is blocked because support payments to the spouse/common-law partner are indicated."
        elif separated_in_year:
            spouse_reason = "Spouse claim is blocked because 'Separated in Year' is checked."
        else:
            spouse_allowed = True
            spouse_reason = "Spouse amount is allowed from the entered household status."
            spouse_auto_amount = calculate_spouse_amount(bpa, spouse_net_income, spouse_infirm)

    eligible_allowed = False
    eligible_reason = "Not requested."
    eligible_auto_amount = 0.0
    if eligible_enabled:
        if spouse_allowed:
            eligible_reason = "Eligible dependant is blocked because the spouse amount is already being claimed."
        elif has_spouse_end_of_year and not separated_in_year:
            eligible_reason = "Eligible dependant is blocked because a spouse/common-law partner is present at year end."
        elif not dependant_lived_with_you:
            eligible_reason = "Eligible dependant is blocked because 'Dependant Lived With You' is not checked."
        elif not qualifies_as_dependant_relative:
            eligible_reason = "Eligible dependant is blocked because the dependant relationship is marked as 'Other'."
        elif paid_child_support_for_dependant and not shared_custody_claim_agreement:
            eligible_reason = "Eligible dependant is blocked because child support is paid and no shared-custody claim agreement is checked."
        elif another_household_member_claims_dependant:
            eligible_reason = "Eligible dependant is blocked because another household member is already claiming the dependant."
        elif dependant_category == "Other":
            eligible_reason = "Eligible dependant is blocked because the dependant category is marked as 'Other'."
        else:
            eligible_allowed = True
            eligible_reason = "Eligible dependant amount is allowed from the entered household status."
            eligible_auto_amount = calculate_eligible_dependant_amount(bpa, eligible_dependant_net_income, eligible_infirm)

    caregiver_base_requested = max(
        value(data, "provincial_caregiver_claim_amount"),
        value(data, "ontario_caregiver_amount"),
    )
    if caregiver_claim_target in {"Auto", "Dependant"}:
        caregiver_base_requested += additional_dependant_caregiver_claim_total
    caregiver_available = caregiver_base_requested
    caregiver_allowed = False
    caregiver_reason = "No caregiver claim amount entered."
    caregiver_claim_amount = 0.0
    if caregiver_base_requested > 0:
        if another_household_member_claims_caregiver:
            caregiver_reason = "Caregiver amount is blocked because another household member is already claiming the caregiver amount."
        elif caregiver_claim_target == "Spouse" and not spouse_infirm:
            caregiver_reason = "Caregiver amount is blocked because the target is set to spouse, but the spouse is not marked infirm."
        elif caregiver_claim_target == "Dependant" and not eligible_infirm:
            caregiver_reason = "Caregiver amount is blocked because the target is set to dependant, but the dependant is not marked infirm."
        elif caregiver_claim_target == "Auto" and spouse_infirm and eligible_infirm:
            caregiver_reason = "Caregiver amount needs a target because both spouse and dependant are marked infirm."
        elif not qualifies_for_caregiver_relationship and not spouse_infirm:
            caregiver_reason = "Caregiver amount is blocked because the dependant relationship is not identified as a qualifying relationship."
        elif eligible_infirm and not is_adult_dependant_category:
            caregiver_reason = "Caregiver amount is blocked because the dependant category does not indicate an adult dependant."
        elif not (spouse_infirm or eligible_infirm):
            caregiver_reason = "Caregiver amount is blocked because no infirm spouse or infirm dependant is indicated."
        elif (
            (caregiver_claim_target == "Spouse" and spouse_infirm and spouse_allowed)
            or (caregiver_claim_target == "Dependant" and eligible_infirm and qualifies_as_dependant_relative)
            or (caregiver_claim_target == "Auto" and ((spouse_infirm and spouse_allowed) or (eligible_infirm and qualifies_as_dependant_relative)))
        ):
            caregiver_allowed = True
            caregiver_reason = "Caregiver amount is allowed based on the entered spouse/dependant household status."
            caregiver_claim_amount = caregiver_base_requested
        else:
            caregiver_reason = "Caregiver amount was entered, but no infirm spouse/dependant or qualifying household relationship is currently indicated."

    disability_transfer_requested = value(data, "ontario_disability_transfer")
    disability_transfer_allowed = False
    disability_transfer_reason = "No disability transfer entered."
    disability_transfer_used = 0.0
    disability_transfer_available = max(
        spouse_disability_transfer_available_effective if disability_transfer_source in {"Auto", "Spouse"} else 0.0,
        dependant_disability_transfer_available_effective if disability_transfer_source in {"Auto", "Dependant"} else 0.0,
    )
    if disability_transfer_requested > 0:
        if another_household_member_claims_disability_transfer:
            disability_transfer_reason = "Disability transfer is blocked because another household member is already claiming the disability transfer."
        elif not qualifies_as_dependant_relative and not has_spouse_end_of_year:
            disability_transfer_reason = "Disability transfer is blocked because the dependant relationship is not identified as a qualifying relationship."
        elif disability_transfer_source == "Auto" and spouse_infirm and eligible_infirm:
            disability_transfer_reason = "Disability transfer needs a source because both spouse and dependant could qualify."
        elif disability_transfer_source == "Spouse" and spouse_infirm and spouse_disability_transfer_available_effective > 0 and has_spouse_end_of_year:
            disability_transfer_allowed = True
            disability_transfer_reason = "Disability transfer is allowed from the entered spouse transfer details."
            disability_transfer_used = min(disability_transfer_requested, spouse_disability_transfer_available_effective)
            disability_transfer_available = spouse_disability_transfer_available_effective
        elif disability_transfer_source == "Dependant" and eligible_infirm and dependant_disability_transfer_available_effective > 0 and qualifies_as_dependant_relative and dependant_lived_with_you:
            disability_transfer_allowed = True
            disability_transfer_reason = "Disability transfer is allowed from the entered dependant transfer details."
            disability_transfer_used = min(disability_transfer_requested, dependant_disability_transfer_available_effective)
            disability_transfer_available = dependant_disability_transfer_available_effective
        elif disability_transfer_source == "Auto" and spouse_infirm and spouse_disability_transfer_available_effective > 0 and has_spouse_end_of_year:
            disability_transfer_allowed = True
            disability_transfer_reason = "Disability transfer is allowed from the entered spouse transfer details."
            disability_transfer_used = min(disability_transfer_requested, spouse_disability_transfer_available_effective)
            disability_transfer_available = spouse_disability_transfer_available_effective
        elif disability_transfer_source == "Auto" and eligible_infirm and dependant_disability_transfer_available_effective > 0 and qualifies_as_dependant_relative and dependant_lived_with_you:
            disability_transfer_allowed = True
            disability_transfer_reason = "Disability transfer is allowed from the entered dependant transfer details."
            disability_transfer_used = min(disability_transfer_requested, dependant_disability_transfer_available_effective)
            disability_transfer_available = dependant_disability_transfer_available_effective
        elif disability_transfer_source == "Spouse" and not spouse_infirm:
            disability_transfer_reason = "Disability transfer is blocked because the source is set to spouse, but the spouse is not marked infirm."
        elif disability_transfer_source == "Dependant" and not eligible_infirm:
            disability_transfer_reason = "Disability transfer is blocked because the source is set to dependant, but the dependant is not marked infirm."
        elif spouse_infirm and spouse_disability_transfer_available_effective == 0.0 and disability_transfer_source in {"Auto", "Spouse"}:
            disability_transfer_reason = "Disability transfer is blocked because no unused spouse disability transfer is indicated."
        elif eligible_infirm and dependant_disability_transfer_available_effective == 0.0 and disability_transfer_source in {"Auto", "Dependant"}:
            disability_transfer_reason = "Disability transfer is blocked because no unused dependant disability transfer is indicated."
        elif eligible_infirm and not dependant_lived_with_you:
            disability_transfer_reason = "Disability transfer is blocked because the dependant is not marked as living with you."
        elif not (spouse_infirm or eligible_infirm):
            disability_transfer_reason = "Disability transfer is blocked because no disabled spouse or disabled dependant is indicated."
        else:
            disability_transfer_reason = "Disability transfer was entered, but no qualifying spouse/dependant household relationship is currently indicated."

    medical_dependants_requested = value(data, "ontario_medical_dependants") + additional_dependant_medical_claim_total
    medical_dependants_allowed = False
    medical_dependants_reason = "No dependant medical amount entered."
    medical_dependants_used = 0.0
    medical_dependants_available = medical_dependants_requested
    if medical_dependants_requested > 0:
        if medical_dependant_claim_shared:
            medical_dependants_reason = "Medical for other dependants is blocked because another person is already sharing or claiming the dependant medical amount."
        elif not qualifies_for_medical_dependant_relationship:
            medical_dependants_reason = "Medical for other dependants is blocked because the dependant relationship is not identified as a qualifying relationship."
        elif is_minor_child_dependant:
            medical_dependants_reason = "Medical for other dependants is blocked because the dependant category is marked as a minor child."
        elif eligible_allowed or dependant_lived_with_you:
            medical_dependants_allowed = True
            medical_dependants_reason = "Medical for other dependants is allowed from the entered dependant relationship."
            medical_dependants_used = medical_dependants_requested
        else:
            medical_dependants_reason = "Medical for other dependants was entered, but no dependant household relationship is currently indicated."

    return {
        "spouse_allowed": spouse_allowed,
        "spouse_reason": spouse_reason,
        "spouse_auto_amount": spouse_auto_amount,
        "eligible_allowed": eligible_allowed,
        "eligible_reason": eligible_reason,
        "eligible_auto_amount": eligible_auto_amount,
        "caregiver_allowed": caregiver_allowed,
        "caregiver_reason": caregiver_reason,
        "caregiver_requested": caregiver_base_requested,
        "caregiver_available": caregiver_available,
        "caregiver_claim_amount": caregiver_claim_amount,
        "disability_transfer_allowed": disability_transfer_allowed,
        "disability_transfer_reason": disability_transfer_reason,
        "disability_transfer_requested": disability_transfer_requested,
        "disability_transfer_available": disability_transfer_available,
        "disability_transfer_used": disability_transfer_used,
        "medical_dependants_allowed": medical_dependants_allowed,
        "medical_dependants_reason": medical_dependants_reason,
        "medical_dependants_requested": medical_dependants_requested,
        "medical_dependants_available": medical_dependants_available,
        "medical_dependants_used": medical_dependants_used,
        "qualifies_as_dependant_relative": qualifies_as_dependant_relative,
        "dependant_category": dependant_category,
    }


def can_claim_eligible_dependant(data: dict[str, Any]) -> bool:
    if not bool(data.get("eligible_dependant_claim_enabled", False)):
        return False
    if bool(data.get("spouse_claim_enabled", False)):
        return False
    if bool(data.get("has_spouse_end_of_year", False)) and not bool(data.get("separated_in_year", False)):
        return False
    if not bool(data.get("dependant_lived_with_you", False)):
        return False
    if bool(data.get("paid_child_support_for_dependant", False)) and not bool(data.get("shared_custody_claim_agreement", False)):
        return False
    if bool(data.get("another_household_member_claims_dependant", False)):
        return False
    return True


def calculate_ontario_health_premium(taxable_income: float) -> float:
    if taxable_income <= 20000:
        return 0.0
    if taxable_income <= 36000:
        return min(300.0, 0.06 * (taxable_income - 20000.0))
    if taxable_income <= 48000:
        return min(450.0, 300.0 + 0.06 * (taxable_income - 36000.0))
    if taxable_income <= 72000:
        return min(600.0, 450.0 + 0.25 * (taxable_income - 48000.0))
    if taxable_income <= 200000:
        return min(750.0, 600.0 + 0.25 * (taxable_income - 72000.0))
    return min(900.0, 750.0 + 0.25 * (taxable_income - 200000.0))


def calculate_provincial_surtax(provincial_tax_after_credits: float, province_params: dict[str, Any]) -> float:
    surtax_rules = province_params.get("surtax")
    if not surtax_rules:
        return 0.0
    surtax = 0.0
    first_threshold, first_rate = surtax_rules[0]
    if provincial_tax_after_credits > first_threshold:
        second_threshold = surtax_rules[1][0] if len(surtax_rules) > 1 else provincial_tax_after_credits
        surtax += (min(provincial_tax_after_credits, second_threshold) - first_threshold) * first_rate
    if len(surtax_rules) > 1:
        second_threshold, second_rate = surtax_rules[1]
        if provincial_tax_after_credits > second_threshold:
            surtax += (provincial_tax_after_credits - second_threshold) * second_rate
    return max(0.0, surtax)


def calculate_provincial_donation_credit(
    province: str,
    tax_year: int,
    donation_amount: float,
    provincial_credit_rate: float,
    top_provincial_rate: float,
    taxable_income: float,
) -> float:
    if donation_amount <= 0:
        return 0.0
    first_portion = min(200.0, donation_amount)
    remaining = max(0.0, donation_amount - first_portion)
    if province == "ON":
        return first_portion * 0.0505 + remaining * 0.1116
    if province == "BC":
        threshold = BC_DONATION_THRESHOLDS.get(tax_year)
        if threshold is None:
            return first_portion * provincial_credit_rate + remaining * 0.168
        high_rate_portion = min(remaining, max(0.0, taxable_income - threshold))
        middle_portion = max(0.0, remaining - high_rate_portion)
        return first_portion * provincial_credit_rate + middle_portion * 0.168 + high_rate_portion * 0.205
    return first_portion * provincial_credit_rate + remaining * top_provincial_rate


def calculate_provincial_dividend_tax_credit(province: str, taxable_eligible_dividends: float, taxable_non_eligible_dividends: float) -> float:
    if province == "ON":
        return taxable_eligible_dividends * ONTARIO_ELIGIBLE_DIVIDEND_CREDIT_RATE + taxable_non_eligible_dividends * ONTARIO_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE
    if province == "BC":
        return taxable_eligible_dividends * BC_ELIGIBLE_DIVIDEND_CREDIT_RATE + taxable_non_eligible_dividends * BC_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE
    if province == "NS":
        return taxable_non_eligible_dividends * NS_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE
    return 0.0


def calculate_provincial_low_income_reduction(province: str, tax_year: int, data: dict[str, Any]) -> dict[str, float]:
    spouse_or_dependant_allowed = bool(data.get("household_spouse_allowed", False)) or bool(
        data.get("household_eligible_dependant_allowed", False)
    )
    if province == "NB":
        config = NB_LOW_INCOME_REDUCTION.get(tax_year)
        if not config:
            return {"credit": 0.0}
        credit = config["spouse_or_eligible_dependant"] if spouse_or_dependant_allowed else 0.0
        return {"credit": credit}
    if province == "NL":
        config = NL_LOW_INCOME_REDUCTION.get(tax_year)
        if not config:
            return {"credit": 0.0}
        credit = config["spouse_or_eligible_dependant"] if spouse_or_dependant_allowed else 0.0
        return {"credit": credit}
    if province == "PE":
        config = PE_LOW_INCOME_REDUCTION.get(tax_year)
        if not config:
            return {"credit": 0.0}
        dependent_children = value(data, "provincial_dependent_children_count")
        credit = dependent_children * config["dependent_child"]
        if spouse_or_dependant_allowed:
            credit += config["spouse_or_eligible_dependant"]
        return {"credit": credit}
    return {"credit": 0.0}


def calculate_nb_seniors_home_renovation_credit(expenses: float) -> float:
    return min(max(0.0, expenses), 10000.0) * 0.10


def calculate_ab_supplemental_tax_credit(base_claim_amounts: float) -> float:
    return max(0.0, (base_claim_amounts - 60000.0) * 0.02)


def calculate_mb_fertility_credit(expenses: float) -> float:
    return min(max(0.0, expenses) * 0.40, 16000.0)
