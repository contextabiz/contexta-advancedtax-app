from __future__ import annotations

from typing import Any

from tax_config import TAX_CONFIGS

from .constants import (
    BC_MEDICAL_THRESHOLDS,
    ELIGIBLE_DIVIDEND_GROSS_UP,
    FEDERAL_AGE_AMOUNTS,
    FEDERAL_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    FEDERAL_MEDICAL_THRESHOLDS,
    FEDERAL_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE,
    MB_FAMILY_TAX_BENEFIT,
    NON_ELIGIBLE_DIVIDEND_GROSS_UP,
    NS_AGE_CREDIT_CONFIG,
    ONTARIO_AGE_AMOUNTS,
    ONTARIO_MEDICAL_DEPENDANT_LIMITS,
    PROVINCIAL_PENSION_AMOUNTS,
    SCHEDULE_9_THRESHOLDS,
)
from .credits import (
    calculate_ab_supplemental_tax_credit,
    calculate_age_amount,
    calculate_bc_tax_reduction,
    calculate_canada_workers_benefit,
    calculate_cwb_disability_supplement,
    calculate_donation_credit,
    calculate_eligible_dependant_amount,
    evaluate_household_claims,
    calculate_lift_credit,
    calculate_mb_fertility_credit,
    calculate_medical_claim,
    calculate_medical_expense_supplement,
    calculate_nb_seniors_home_renovation_credit,
    calculate_ontario_fertility_credit,
    calculate_ontario_health_premium,
    calculate_ontario_seniors_transit_credit,
    calculate_payroll_overpayment_refunds,
    calculate_pe_volunteer_credit,
    calculate_bc_home_renovation_credit,
    calculate_bc_renters_credit,
    calculate_provincial_dividend_tax_credit,
    calculate_provincial_donation_credit,
    calculate_provincial_low_income_reduction,
    calculate_sk_fertility_credit,
    calculate_provincial_surtax,
    calculate_spouse_amount,
    can_claim_eligible_dependant,
)
from .utils import calculate_federal_bpa, calculate_progressive_tax, estimate_employee_cpp_ei, value


def calculate_schedule_9_credit(
    tax_year: int,
    total_regular_donations: float,
    ecological_cultural_gifts: float,
    ecological_gifts_pre2016: float,
    taxable_income: float,
    credit_rate: float,
) -> dict[str, float]:
    first_200 = min(200.0, max(0.0, total_regular_donations + ecological_cultural_gifts))
    amount_above_200 = max(0.0, (total_regular_donations + ecological_cultural_gifts) - first_200)
    threshold = SCHEDULE_9_THRESHOLDS.get(tax_year)
    if threshold is None:
        federal_credit = calculate_donation_credit(total_regular_donations + ecological_cultural_gifts, credit_rate)
        return {
            "first_200": first_200,
            "amount_above_200": amount_above_200,
            "high_rate_portion": 0.0,
            "federal_credit": federal_credit,
            "ontario_credit": first_200 * 0.0505 + amount_above_200 * 0.1116,
        }
    line16 = max(0.0, amount_above_200 - ecological_gifts_pre2016)
    line19 = max(0.0, taxable_income - threshold)
    high_rate_portion = min(line16, line19)
    remaining_29_portion = max(0.0, amount_above_200 - high_rate_portion)
    federal_credit = high_rate_portion * 0.33 + remaining_29_portion * 0.29 + first_200 * credit_rate
    ontario_credit = first_200 * 0.0505 + amount_above_200 * 0.1116
    return {
        "first_200": first_200,
        "amount_above_200": amount_above_200,
        "high_rate_portion": high_rate_portion,
        "remaining_29_portion": remaining_29_portion,
        "federal_credit": federal_credit,
        "ontario_credit": ontario_credit,
    }


def allocate_schedule_9_regular_donations(
    net_income: float,
    current_year_available: float,
    current_year_requested: float,
    carryforward_available: float,
    carryforward_requested: float,
) -> dict[str, float]:
    regular_limit = max(0.0, net_income * 0.75)
    carryforward_requested_capped = min(carryforward_available, max(0.0, carryforward_requested))
    carryforward_used = min(carryforward_requested_capped, regular_limit)
    remaining_limit = max(0.0, regular_limit - carryforward_used)
    current_year_requested_capped = min(current_year_available, max(0.0, current_year_requested))
    current_year_used = min(current_year_requested_capped, remaining_limit)
    return {
        "regular_limit": regular_limit,
        "carryforward_requested_capped": carryforward_requested_capped,
        "carryforward_used": carryforward_used,
        "carryforward_unused": max(0.0, carryforward_available - carryforward_used),
        "current_year_requested_capped": current_year_requested_capped,
        "current_year_used": current_year_used,
        "current_year_unused": max(0.0, current_year_available - current_year_used),
        "total_regular_claimed": carryforward_used + current_year_used,
        "total_regular_unused": max(0.0, current_year_available - current_year_used) + max(0.0, carryforward_available - carryforward_used),
    }


def calculate_personal_tax_return(data: dict[str, Any]) -> dict[str, float]:
    tax_year = int(data["tax_year"])
    province = str(data["province"])
    age = value(data, "age")
    params = TAX_CONFIGS[tax_year]
    province_params = params["provincial"][province]

    employment_income = value(data, "employment_income")
    pension_income = value(data, "pension_income")
    rrsp_rrif_income = value(data, "rrsp_rrif_income")
    other_income = value(data, "other_income")
    schedule_net_rental_income = value(data, "t776_net_rental_income_before_manual")
    net_rental_income_input = value(data, "net_rental_income")
    manual_net_rental_income = value(data, "manual_net_rental_income")
    if schedule_net_rental_income or manual_net_rental_income:
        net_rental_income = schedule_net_rental_income + manual_net_rental_income
    else:
        net_rental_income = net_rental_income_input
    schedule_taxable_capital_gains = value(data, "schedule3_taxable_capital_gains_before_manual")
    taxable_capital_gains_input = value(data, "taxable_capital_gains")
    manual_taxable_capital_gains = value(data, "manual_taxable_capital_gains")
    if schedule_taxable_capital_gains or manual_taxable_capital_gains:
        taxable_capital_gains = schedule_taxable_capital_gains + manual_taxable_capital_gains
    else:
        taxable_capital_gains = taxable_capital_gains_input
    interest_income = value(data, "interest_income")
    eligible_dividends = value(data, "eligible_dividends")
    non_eligible_dividends = value(data, "non_eligible_dividends")
    t5_eligible_dividends_taxable = value(data, "t5_eligible_dividends_taxable")
    t5_non_eligible_dividends_taxable = value(data, "t5_non_eligible_dividends_taxable")
    t5_federal_dividend_credit = value(data, "t5_federal_dividend_credit")
    t3_eligible_dividends_taxable = value(data, "t3_eligible_dividends_taxable")
    t3_non_eligible_dividends_taxable = value(data, "t3_non_eligible_dividends_taxable")
    t3_federal_dividend_credit = value(data, "t3_federal_dividend_credit")
    spouse_net_income = value(data, "spouse_net_income")
    eligible_dependant_net_income = value(data, "eligible_dependant_net_income")
    additional_dependant_count = value(data, "additional_dependant_count")
    additional_dependant_caregiver_claim_total = value(data, "additional_dependant_caregiver_claim_total")
    additional_dependant_disability_transfer_available_total = value(data, "additional_dependant_disability_transfer_available_total")
    additional_dependant_medical_claim_total = value(data, "additional_dependant_medical_claim_total")
    foreign_income = value(data, "foreign_income")
    foreign_tax_paid = value(data, "foreign_tax_paid")
    t2209_non_business_tax_paid = value(data, "t2209_non_business_tax_paid") or foreign_tax_paid
    t2209_net_foreign_non_business_income = value(data, "t2209_net_foreign_non_business_income") or foreign_income
    t2209_net_income_override = value(data, "t2209_net_income_override")
    t2209_basic_federal_tax_override = value(data, "t2209_basic_federal_tax_override")
    t2036_provincial_tax_otherwise_payable_override = value(data, "t2036_provincial_tax_otherwise_payable_override")
    provincial_dividend_tax_credit_manual = max(
        value(data, "provincial_dividend_tax_credit_manual"),
        value(data, "ontario_dividend_tax_credit_manual"),
    )
    spouse_claim_enabled = bool(data.get("spouse_claim_enabled", False))
    spouse_infirm = bool(data.get("spouse_infirm", False))
    eligible_dependant_claim_enabled = bool(data.get("eligible_dependant_claim_enabled", False))
    eligible_dependant_infirm = bool(data.get("eligible_dependant_infirm", False))
    has_spouse_end_of_year = bool(data.get("has_spouse_end_of_year", False))
    rdsp_repayment = value(data, "rdsp_repayment")
    universal_child_care_benefit = value(data, "universal_child_care_benefit")
    rdsp_income = value(data, "rdsp_income")
    spouse_line_21300 = value(data, "spouse_line_21300")
    spouse_rdsp_repayment = value(data, "spouse_rdsp_repayment")
    spouse_uccb = value(data, "spouse_uccb")
    spouse_rdsp_income = value(data, "spouse_rdsp_income")
    donations_eligible_total = value(data, "donations_eligible_total")
    schedule9_current_year_donations_available = value(data, "schedule9_current_year_donations_available")
    schedule9_current_year_donations_claim_requested = value(data, "schedule9_current_year_donations_claim_requested")
    schedule9_carryforward_available = value(data, "schedule9_carryforward_available")
    schedule9_carryforward_claim_requested = value(data, "schedule9_carryforward_claim_requested")
    ecological_cultural_gifts = value(data, "ecological_cultural_gifts")
    ecological_gifts_pre2016 = value(data, "ecological_gifts_pre2016")
    mb479_personal_tax_credit = value(data, "mb479_personal_tax_credit")
    mb479_homeowners_affordability_credit = value(data, "mb479_homeowners_affordability_credit")
    mb479_renters_affordability_credit = value(data, "mb479_renters_affordability_credit")
    mb479_seniors_school_rebate = value(data, "mb479_seniors_school_rebate")
    mb479_primary_caregiver_credit = value(data, "mb479_primary_caregiver_credit")
    mb479_fertility_treatment_expenses = value(data, "mb479_fertility_treatment_expenses")
    ns479_volunteer_credit = value(data, "ns479_volunteer_credit")
    ns479_childrens_sports_arts_credit = value(data, "ns479_childrens_sports_arts_credit")
    nb_political_contribution_credit = value(data, "nb_political_contribution_credit")
    nb_small_business_investor_credit = value(data, "nb_small_business_investor_credit")
    nb_lsvcc_credit = value(data, "nb_lsvcc_credit")
    nb_seniors_home_renovation_expenses = value(data, "nb_seniors_home_renovation_expenses")
    nl_political_contribution_credit = value(data, "nl_political_contribution_credit")
    nl_direct_equity_credit = value(data, "nl_direct_equity_credit")
    nl_resort_property_credit = value(data, "nl_resort_property_credit")
    nl_venture_capital_credit = value(data, "nl_venture_capital_credit")
    nl_unused_venture_capital_credit = value(data, "nl_unused_venture_capital_credit")
    nl479_other_refundable_credits = value(data, "nl479_other_refundable_credits")
    ontario_fertility_treatment_expenses = value(data, "ontario_fertility_treatment_expenses")
    ontario_seniors_public_transit_expenses = value(data, "ontario_seniors_public_transit_expenses")
    bc_renters_credit_eligible = bool(data.get("bc_renters_credit_eligible", False))
    bc_home_renovation_expenses = value(data, "bc_home_renovation_expenses")
    bc_home_renovation_eligible = bool(data.get("bc_home_renovation_eligible", False))
    sk_fertility_treatment_expenses = value(data, "sk_fertility_treatment_expenses")
    pe_volunteer_credit_eligible = bool(data.get("pe_volunteer_credit_eligible", False))
    canada_workers_benefit = value(data, "canada_workers_benefit")
    cwb_disability_supplement_eligible = bool(data.get("cwb_disability_supplement_eligible", False))
    spouse_cwb_disability_supplement_eligible = bool(data.get("spouse_cwb_disability_supplement_eligible", False))
    canada_training_credit_limit_available = value(data, "canada_training_credit_limit_available")
    canada_training_credit = value(data, "canada_training_credit")
    medical_expense_supplement = value(data, "medical_expense_supplement")
    other_federal_refundable_credits = value(data, "other_federal_refundable_credits")
    manual_provincial_refundable_credits = value(data, "manual_provincial_refundable_credits")
    other_manual_refundable_credits = value(data, "other_manual_refundable_credits")
    schedule11_current_year_tuition_available = value(data, "schedule11_current_year_tuition_available")
    schedule11_carryforward_available = value(data, "schedule11_carryforward_available")
    schedule11_current_year_claim_requested = value(data, "schedule11_current_year_claim_requested")
    schedule11_carryforward_claim_requested = value(data, "schedule11_carryforward_claim_requested")
    schedule11_transfer_from_spouse = value(data, "schedule11_transfer_from_spouse")
    schedule11_current_year_claim_used = min(
        schedule11_current_year_tuition_available,
        max(0.0, schedule11_current_year_claim_requested),
    )
    schedule11_current_year_unused = max(
        0.0,
        schedule11_current_year_tuition_available - schedule11_current_year_claim_used,
    )
    schedule11_carryforward_claim_used = min(
        schedule11_carryforward_available,
        max(0.0, schedule11_carryforward_claim_requested),
    )
    schedule11_carryforward_unused = max(
        0.0,
        schedule11_carryforward_available - schedule11_carryforward_claim_used,
    )
    schedule11_total_available = (
        schedule11_current_year_tuition_available + schedule11_carryforward_available
    )
    schedule11_total_claim_used = (
        schedule11_current_year_claim_used + schedule11_carryforward_claim_used
    )
    schedule11_total_unused = (
        schedule11_current_year_unused + schedule11_carryforward_unused
    )
    net_capital_loss_carryforward_requested = value(data, "net_capital_loss_carryforward")
    net_capital_loss_carryforward_used = min(
        net_capital_loss_carryforward_requested,
        max(0.0, taxable_capital_gains),
    )
    net_capital_loss_carryforward_unused = max(
        0.0,
        net_capital_loss_carryforward_requested - net_capital_loss_carryforward_used,
    )

    grossed_up_eligible_dividends = eligible_dividends * ELIGIBLE_DIVIDEND_GROSS_UP
    grossed_up_non_eligible_dividends = non_eligible_dividends * NON_ELIGIBLE_DIVIDEND_GROSS_UP
    taxable_eligible_dividends = (
        grossed_up_eligible_dividends
        + t5_eligible_dividends_taxable
        + t3_eligible_dividends_taxable
    )
    taxable_non_eligible_dividends = (
        grossed_up_non_eligible_dividends
        + t5_non_eligible_dividends_taxable
        + t3_non_eligible_dividends_taxable
    )

    total_income = (
        employment_income
        + pension_income
        + rrsp_rrif_income
        + other_income
        + net_rental_income
        + taxable_capital_gains
        + interest_income
        + taxable_eligible_dividends
        + taxable_non_eligible_dividends
    )

    employee_payroll = estimate_employee_cpp_ei(employment_income, params)
    cpp_credit_base = employee_payroll["employee_cpp_base"]
    cpp_deduction = employee_payroll["employee_cpp_enhanced"]
    total_cpp = employee_payroll["employee_cpp_total"]
    ei = employee_payroll["ei"]

    total_deductions = (
        value(data, "rrsp_deduction")
        + value(data, "fhsa_deduction")
        + value(data, "rpp_contribution")
        + value(data, "union_dues")
        + value(data, "child_care_expenses")
        + value(data, "moving_expenses")
        + value(data, "support_payments_deduction")
        + value(data, "carrying_charges")
        + value(data, "other_employment_expenses")
        + value(data, "other_deductions")
        + cpp_deduction
    )

    net_income = max(0.0, total_income - total_deductions)
    taxable_income = max(
        0.0,
        net_income
        - net_capital_loss_carryforward_used
        - value(data, "other_loss_carryforward"),
    )
    adjusted_net_income_for_lift = max(0.0, net_income + value(data, "line_21300") + rdsp_repayment - universal_child_care_benefit - rdsp_income)
    spouse_adjusted_net_income_for_lift = max(
        0.0,
        spouse_net_income + spouse_line_21300 + spouse_rdsp_repayment - spouse_uccb - spouse_rdsp_income,
    )

    federal_age_amount_auto = 0.0
    federal_bpa = calculate_federal_bpa(net_income, params)
    if tax_year in FEDERAL_AGE_AMOUNTS:
        federal_age_amount_auto = calculate_age_amount(age, net_income, FEDERAL_AGE_AMOUNTS[tax_year])

    schedule9_regular_allocation = allocate_schedule_9_regular_donations(
        net_income=net_income,
        current_year_available=schedule9_current_year_donations_available,
        current_year_requested=schedule9_current_year_donations_claim_requested,
        carryforward_available=schedule9_carryforward_available,
        carryforward_requested=schedule9_carryforward_claim_requested,
    )
    schedule9_current_year_donations_claim_used = schedule9_regular_allocation["current_year_used"]
    schedule9_current_year_donations_unused = schedule9_regular_allocation["current_year_unused"]
    schedule9_carryforward_claim_used = schedule9_regular_allocation["carryforward_used"]
    schedule9_carryforward_unused = schedule9_regular_allocation["carryforward_unused"]
    schedule9_total_regular_donations_claimed = schedule9_regular_allocation["total_regular_claimed"]
    schedule9_total_regular_donations_unused = schedule9_regular_allocation["total_regular_unused"]

    provincial_age_amount_auto = 0.0
    if province == "ON" and tax_year in ONTARIO_AGE_AMOUNTS:
        provincial_age_amount_auto = calculate_age_amount(age, net_income, ONTARIO_AGE_AMOUNTS[tax_year])
    elif province == "NS":
        ns_age_config = NS_AGE_CREDIT_CONFIG.get(tax_year)
        if ns_age_config and age >= 65 and taxable_income < ns_age_config["taxable_income_limit"]:
            provincial_age_amount_auto = ns_age_config["credit_amount"]

    medical_expenses_total = value(data, "medical_expenses_paid")
    federal_medical_claim = value(data, "medical_expenses_eligible")
    if tax_year in FEDERAL_MEDICAL_THRESHOLDS:
        federal_medical_claim = calculate_medical_claim(
            medical_expenses_total,
            net_income,
            FEDERAL_MEDICAL_THRESHOLDS[tax_year],
        )

    provincial_medical_claim = federal_medical_claim
    if province == "ON" and tax_year in FEDERAL_MEDICAL_THRESHOLDS:
        provincial_medical_claim = calculate_medical_claim(
            medical_expenses_total,
            net_income,
            FEDERAL_MEDICAL_THRESHOLDS[tax_year],
        )
    elif province == "BC" and tax_year in BC_MEDICAL_THRESHOLDS:
        provincial_medical_claim = calculate_medical_claim(
            medical_expenses_total,
            net_income,
            BC_MEDICAL_THRESHOLDS[tax_year],
        )

    household_claims = evaluate_household_claims(data, federal_bpa)
    auto_spouse_amount = household_claims["spouse_auto_amount"]
    auto_eligible_dependant_amount = household_claims["eligible_auto_amount"]
    auto_canada_workers_benefit = calculate_canada_workers_benefit(
        tax_year=tax_year,
        working_income=employment_income,
        adjusted_net_income=adjusted_net_income_for_lift,
        spouse_adjusted_net_income=spouse_adjusted_net_income_for_lift,
        has_spouse=has_spouse_end_of_year,
    )
    auto_cwb_disability_supplement = calculate_cwb_disability_supplement(
        tax_year=tax_year,
        adjusted_net_income=adjusted_net_income_for_lift,
        spouse_adjusted_net_income=spouse_adjusted_net_income_for_lift,
        has_spouse=has_spouse_end_of_year,
        is_disabled=cwb_disability_supplement_eligible,
        spouse_is_disabled=spouse_cwb_disability_supplement_eligible,
    )
    auto_canada_training_credit = min(
        canada_training_credit_limit_available,
        schedule11_current_year_claim_used,
    )
    auto_medical_expense_supplement = calculate_medical_expense_supplement(
        tax_year=tax_year,
        employment_income=employment_income,
        net_income=net_income,
        medical_claim=federal_medical_claim,
    )
    manual_spouse_claim = value(data, "spouse_amount_claim")
    manual_eligible_dependant_claim = value(data, "eligible_dependant_claim")
    caregiver_claim_target = str(data.get("caregiver_claim_target", "Auto"))
    disability_transfer_source = str(data.get("disability_transfer_source", "Auto"))
    effective_spouse_claim = max(manual_spouse_claim, auto_spouse_amount) if household_claims["spouse_allowed"] else 0.0
    effective_eligible_dependant_claim = (
        max(manual_eligible_dependant_claim, auto_eligible_dependant_amount)
        if household_claims["eligible_allowed"]
        else 0.0
    )
    effective_disability_transfer = household_claims["disability_transfer_used"]

    household_low_income_context = dict(data)
    household_low_income_context["household_spouse_allowed"] = household_claims["spouse_allowed"]
    household_low_income_context["household_eligible_dependant_allowed"] = household_claims["eligible_allowed"]

    federal_basic_tax = calculate_progressive_tax(taxable_income, params["federal_brackets"])
    provincial_basic_tax = calculate_progressive_tax(taxable_income, province_params["brackets"])

    federal_credit_rate = params["federal_credit_rate"]
    provincial_credit_rate = province_params["credit_rate"]

    federal_dividend_tax_credit = (
        taxable_eligible_dividends * FEDERAL_ELIGIBLE_DIVIDEND_CREDIT_RATE
        + taxable_non_eligible_dividends * FEDERAL_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE
    )
    if t5_federal_dividend_credit or t3_federal_dividend_credit:
        federal_dividend_tax_credit = (
            t5_federal_dividend_credit
            + t3_federal_dividend_credit
            + grossed_up_eligible_dividends * FEDERAL_ELIGIBLE_DIVIDEND_CREDIT_RATE
            + grossed_up_non_eligible_dividends * FEDERAL_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE
        )

    donation_credit = calculate_schedule_9_credit(
        tax_year=tax_year,
        total_regular_donations=max(
            schedule9_total_regular_donations_claimed,
            donations_eligible_total,
            value(data, "charitable_donations"),
        ),
        ecological_cultural_gifts=ecological_cultural_gifts,
        ecological_gifts_pre2016=ecological_gifts_pre2016,
        taxable_income=taxable_income,
        credit_rate=federal_credit_rate,
    )

    federal_non_refundable_credits = (
        federal_bpa * federal_credit_rate
        + min(employment_income, params["canada_employment_amount_max"]) * federal_credit_rate
        + (cpp_credit_base + ei) * federal_credit_rate
        + effective_spouse_claim * federal_credit_rate
        + effective_eligible_dependant_claim * federal_credit_rate
        + value(data, "disability_amount_claim") * federal_credit_rate
        + max(value(data, "age_amount_claim"), federal_age_amount_auto) * federal_credit_rate
        + (schedule11_total_claim_used + value(data, "tuition_transfer_from_spouse")) * federal_credit_rate
        + value(data, "student_loan_interest") * federal_credit_rate
        + federal_medical_claim * federal_credit_rate
        + value(data, "additional_federal_credits") * federal_credit_rate
        + donation_credit["federal_credit"]
        + federal_dividend_tax_credit
    )

    provincial_pension_amount = 0.0
    pension_config = PROVINCIAL_PENSION_AMOUNTS.get(province, {})
    if tax_year in pension_config:
        provincial_pension_amount = min(pension_income, pension_config[tax_year])

    ontario_medical_dependants = value(data, "ontario_medical_dependants")
    provincial_medical_dependant_claim = 0.0
    if province == "ON" and tax_year in ONTARIO_MEDICAL_DEPENDANT_LIMITS:
        provincial_medical_dependant_claim = min(
            household_claims["medical_dependants_used"],
            ONTARIO_MEDICAL_DEPENDANT_LIMITS[tax_year],
        )

    provincial_caregiver_claim_amount = household_claims["caregiver_claim_amount"]
    provincial_dependant_children_count = value(data, "provincial_dependent_children_count")
    provincial_tax_reduction = 0.0
    provincial_tax_reduction_max = 0.0
    provincial_tax_reduction_base = 0.0
    ontario_child_reduction = value(data, "ontario_dependent_children_count") * 544.0 if province == "ON" else 0.0
    ontario_impairment_reduction = value(data, "ontario_dependant_impairment_count") * 544.0 if province == "ON" else 0.0
    provincial_tax_reduction += ontario_child_reduction + ontario_impairment_reduction
    provincial_dividend_tax_credit_auto = calculate_provincial_dividend_tax_credit(
        province,
        taxable_eligible_dividends,
        taxable_non_eligible_dividends,
    )
    provincial_dividend_tax_credit = max(
        provincial_dividend_tax_credit_manual,
        provincial_dividend_tax_credit_auto,
    )
    if province == "BC":
        bc_tax_reduction = calculate_bc_tax_reduction(tax_year, net_income)
        provincial_tax_reduction += bc_tax_reduction["credit"]
        provincial_tax_reduction_max = bc_tax_reduction["max_credit"]
        provincial_tax_reduction_base = bc_tax_reduction["reduction_base"]
    if province == "MB":
        mb_config = MB_FAMILY_TAX_BENEFIT.get(tax_year)
        if mb_config:
            provincial_tax_reduction += provincial_dependant_children_count * mb_config["dependent_child_amount"] * provincial_credit_rate

    low_income_reduction = calculate_provincial_low_income_reduction(province, tax_year, household_low_income_context)
    provincial_tax_reduction += low_income_reduction["credit"]

    top_provincial_rate = max(rate for _, rate in province_params["brackets"])
    provincial_donation_credit = calculate_provincial_donation_credit(
        province=province,
        tax_year=tax_year,
        donation_amount=max(donations_eligible_total, value(data, "charitable_donations")),
        provincial_credit_rate=provincial_credit_rate,
        top_provincial_rate=top_provincial_rate,
        taxable_income=taxable_income,
    )

    ab_supplemental_tax_credit = 0.0
    if province == "AB":
        ab_supplemental_base = (
            province_params["basic_personal_amount"]
            + effective_spouse_claim
            + effective_eligible_dependant_claim
            + value(data, "disability_amount_claim")
            + provincial_pension_amount
            + provincial_caregiver_claim_amount
        )
        ab_supplemental_tax_credit = calculate_ab_supplemental_tax_credit(ab_supplemental_base)

    nb_special_non_refundable_credits = (
        nb_political_contribution_credit
        + nb_small_business_investor_credit
        + nb_lsvcc_credit
    ) if province == "NB" else 0.0
    nl_special_non_refundable_credits = (
        nl_political_contribution_credit
        + nl_direct_equity_credit
        + nl_resort_property_credit
        + nl_venture_capital_credit
        + nl_unused_venture_capital_credit
    ) if province == "NL" else 0.0

    provincial_basic_personal_credit = province_params["basic_personal_amount"] * provincial_credit_rate
    provincial_basic_personal_claim = province_params["basic_personal_amount"]
    provincial_cpp_ei_claim = cpp_credit_base + ei
    provincial_cpp_ei_credit = (cpp_credit_base + ei) * provincial_credit_rate
    provincial_age_claim = provincial_age_amount_auto
    provincial_age_credit = provincial_age_amount_auto * provincial_credit_rate
    provincial_pension_claim = provincial_pension_amount
    provincial_pension_credit = provincial_pension_amount * provincial_credit_rate
    provincial_spouse_claim = effective_spouse_claim
    provincial_spouse_credit = effective_spouse_claim * provincial_credit_rate
    provincial_eligible_dependant_claim = effective_eligible_dependant_claim
    provincial_eligible_dependant_credit = effective_eligible_dependant_claim * provincial_credit_rate
    provincial_disability_claim = value(data, "disability_amount_claim") + effective_disability_transfer
    provincial_disability_credit = (value(data, "disability_amount_claim") + effective_disability_transfer) * provincial_credit_rate
    provincial_caregiver_claim = provincial_caregiver_claim_amount
    provincial_caregiver_credit = provincial_caregiver_claim_amount * provincial_credit_rate
    provincial_medical_claim_base = provincial_medical_claim
    provincial_medical_credit = provincial_medical_claim * provincial_credit_rate
    provincial_medical_dependant_claim_base = provincial_medical_dependant_claim
    provincial_medical_dependant_credit = provincial_medical_dependant_claim * provincial_credit_rate
    provincial_student_claim = value(data, "ontario_student_loan_interest") + value(data, "ontario_tuition_transfer")
    provincial_student_credit = (value(data, "ontario_student_loan_interest") + value(data, "ontario_tuition_transfer")) * provincial_credit_rate
    provincial_adoption_claim = value(data, "ontario_adoption_expenses")
    provincial_adoption_credit = value(data, "ontario_adoption_expenses") * provincial_credit_rate
    provincial_additional_credit = value(data, "additional_provincial_credit_amount")

    provincial_non_refundable_credits = (
        provincial_basic_personal_credit
        + provincial_cpp_ei_credit
        + provincial_age_credit
        + provincial_pension_credit
        + provincial_spouse_credit
        + provincial_eligible_dependant_credit
        + provincial_disability_credit
        + provincial_caregiver_credit
        + provincial_medical_credit
        + provincial_medical_dependant_credit
        + provincial_donation_credit
        + provincial_student_credit
        + provincial_adoption_credit
        + provincial_additional_credit
        + ab_supplemental_tax_credit
        + nb_special_non_refundable_credits
        + nl_special_non_refundable_credits
    )

    federal_tax = max(0.0, federal_basic_tax - federal_non_refundable_credits)
    provincial_tax_before_surtax = max(0.0, provincial_basic_tax - provincial_non_refundable_credits)
    provincial_surtax = calculate_provincial_surtax(provincial_tax_before_surtax, province_params)
    provincial_health_premium = (
        calculate_ontario_health_premium(taxable_income)
        if province_params.get("health_premium") == "ontario"
        else 0.0
    )
    provincial_tax_after_non_refundable_credits = provincial_tax_before_surtax
    provincial_tax_after_surtax = provincial_tax_after_non_refundable_credits + provincial_surtax
    provincial_tax_after_dividend_credit = max(0.0, provincial_tax_after_surtax - provincial_dividend_tax_credit)
    provincial_tax_after_reduction = max(0.0, provincial_tax_after_dividend_credit - provincial_tax_reduction)
    provincial_tax = provincial_tax_after_reduction

    t2209_net_income = t2209_net_income_override or net_income
    t2209_basic_federal_tax = t2209_basic_federal_tax_override or federal_tax
    t2209_foreign_income_ratio = (
        t2209_net_foreign_non_business_income / t2209_net_income
        if t2209_net_income > 0
        else 0.0
    )
    t2209_limit_before_property_cap = t2209_foreign_income_ratio * t2209_basic_federal_tax
    t2209_limit = t2209_limit_before_property_cap
    foreign_property_limit = t2209_net_foreign_non_business_income * 0.15
    federal_foreign_tax_credit = min(
        t2209_non_business_tax_paid,
        t2209_limit,
        foreign_property_limit,
    )
    t2036_line1 = max(0.0, t2209_non_business_tax_paid - federal_foreign_tax_credit)
    provincial_tax_otherwise_payable = (
        t2036_provincial_tax_otherwise_payable_override
        or provincial_tax
    )
    t2036_foreign_income_ratio = t2209_foreign_income_ratio
    t2036_limit = t2036_foreign_income_ratio * provincial_tax_otherwise_payable
    provincial_foreign_tax_credit = min(
        t2036_line1,
        t2036_limit,
    )
    t2036_unused_foreign_tax = max(0.0, t2036_line1 - provincial_foreign_tax_credit)
    federal_tax = max(0.0, federal_tax - federal_foreign_tax_credit)
    provincial_tax_after_foreign_tax_credit = max(0.0, provincial_tax - provincial_foreign_tax_credit)
    provincial_tax = provincial_tax_after_foreign_tax_credit
    lift_credit = calculate_lift_credit(
        tax_year=tax_year,
        employment_income_line_10100=employment_income,
        self_employment_income_line_10400=0.0,
        adjusted_net_income=adjusted_net_income_for_lift,
        spouse_adjusted_net_income=spouse_adjusted_net_income_for_lift,
        has_spouse=has_spouse_end_of_year,
    )
    provincial_tax_after_lift_credit = max(0.0, provincial_tax - lift_credit["credit"])
    provincial_tax_before_health_premium = provincial_tax_after_lift_credit
    provincial_tax = provincial_tax_before_health_premium + provincial_health_premium

    total_payable = federal_tax + provincial_tax

    income_tax_withheld = value(data, "income_tax_withheld")
    cpp_withheld_total = value(data, "cpp_withheld_total")
    ei_withheld_total = value(data, "ei_withheld_total")
    installments_paid = value(data, "installments_paid")
    other_payments = value(data, "other_payments")
    mb479_fertility_credit = calculate_mb_fertility_credit(mb479_fertility_treatment_expenses) if province == "MB" else 0.0
    nb_seniors_home_renovation_credit = calculate_nb_seniors_home_renovation_credit(nb_seniors_home_renovation_expenses) if province == "NB" else 0.0
    ontario_fertility_credit = calculate_ontario_fertility_credit(tax_year, ontario_fertility_treatment_expenses) if province == "ON" else 0.0
    ontario_seniors_transit_credit = calculate_ontario_seniors_transit_credit(tax_year, ontario_seniors_public_transit_expenses, age) if province == "ON" else 0.0
    bc_renters_credit = (
        calculate_bc_renters_credit(
            tax_year=tax_year,
            adjusted_family_net_income=adjusted_net_income_for_lift + (spouse_adjusted_net_income_for_lift if has_spouse_end_of_year else 0.0),
            eligible=bc_renters_credit_eligible,
        )
        if province == "BC"
        else {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    )
    bc_home_renovation_credit = calculate_bc_home_renovation_credit(
        tax_year,
        bc_home_renovation_expenses,
        bc_home_renovation_eligible,
    ) if province == "BC" else 0.0
    sk_fertility_credit = calculate_sk_fertility_credit(sk_fertility_treatment_expenses) if province == "SK" else 0.0
    pe_volunteer_credit = calculate_pe_volunteer_credit(pe_volunteer_credit_eligible) if province == "PE" else 0.0
    provincial_special_refundable_credits = 0.0
    if province == "MB":
        provincial_special_refundable_credits = (
            mb479_personal_tax_credit
            + mb479_homeowners_affordability_credit
            + mb479_renters_affordability_credit
            + mb479_seniors_school_rebate
            + mb479_primary_caregiver_credit
            + mb479_fertility_credit
        )
    elif province == "NS":
        provincial_special_refundable_credits = ns479_volunteer_credit + ns479_childrens_sports_arts_credit
    elif province == "NB":
        provincial_special_refundable_credits = nb_seniors_home_renovation_credit
    elif province == "NL":
        provincial_special_refundable_credits = nl479_other_refundable_credits
    elif province == "ON":
        provincial_special_refundable_credits = ontario_fertility_credit + ontario_seniors_transit_credit
    elif province == "BC":
        provincial_special_refundable_credits = bc_renters_credit["credit"] + bc_home_renovation_credit
    elif province == "SK":
        provincial_special_refundable_credits = sk_fertility_credit
    elif province == "PE":
        provincial_special_refundable_credits = pe_volunteer_credit
    canada_workers_benefit_auto_total = auto_canada_workers_benefit["credit"] + auto_cwb_disability_supplement["credit"]
    canada_workers_benefit_used = canada_workers_benefit if canada_workers_benefit > 0 else canada_workers_benefit_auto_total
    canada_training_credit_used = canada_training_credit if canada_training_credit > 0 else auto_canada_training_credit
    medical_expense_supplement_used = (
        medical_expense_supplement if medical_expense_supplement > 0 else auto_medical_expense_supplement["credit"]
    )
    payroll_overpayment_refunds = calculate_payroll_overpayment_refunds(
        cpp_withheld=cpp_withheld_total,
        ei_withheld=ei_withheld_total,
        expected_cpp=total_cpp,
        expected_ei=ei,
    )
    federal_refundable_credits = (
        canada_workers_benefit_used
        + canada_training_credit_used
        + medical_expense_supplement_used
        + payroll_overpayment_refunds["total_refund"]
        + other_federal_refundable_credits
    )
    manual_refundable_credits_total = (
        federal_refundable_credits
        + manual_provincial_refundable_credits
        + other_manual_refundable_credits
    )
    refundable_credits = manual_refundable_credits_total + provincial_special_refundable_credits
    total_payments = income_tax_withheld + installments_paid + other_payments + refundable_credits
    refund_or_balance = total_payments - total_payable

    return {
        "total_income": total_income,
        "total_deductions": total_deductions,
        "net_income": net_income,
        "taxable_income": taxable_income,
        "line_10100": employment_income,
        "line_pension_income": pension_income,
        "line_rrsp_rrif_income": rrsp_rrif_income,
        "line_interest_income": interest_income,
        "line_rental_income": net_rental_income,
        "line_taxable_capital_gains": taxable_capital_gains,
        "line_other_income": other_income,
        "additional_dependant_count": additional_dependant_count,
        "additional_dependant_caregiver_claim_total": additional_dependant_caregiver_claim_total,
        "additional_dependant_disability_transfer_available_total": additional_dependant_disability_transfer_available_total,
        "additional_dependant_medical_claim_total": additional_dependant_medical_claim_total,
        "line_rrsp_deduction": value(data, "rrsp_deduction"),
        "line_fhsa_deduction": value(data, "fhsa_deduction"),
        "line_carrying_charges": value(data, "carrying_charges"),
        "line_moving_expenses": value(data, "moving_expenses"),
        "line_support_payments_deduction": value(data, "support_payments_deduction"),
        "line_child_care_expenses": value(data, "child_care_expenses"),
        "line_union_dues": value(data, "union_dues"),
        "line_other_employment_expenses": value(data, "other_employment_expenses"),
        "manual_net_rental_income": manual_net_rental_income,
        "schedule11_current_year_tuition_available": schedule11_current_year_tuition_available,
        "schedule11_carryforward_available": schedule11_carryforward_available,
        "schedule11_total_available": schedule11_total_available,
        "schedule11_current_year_claim_requested": schedule11_current_year_claim_requested,
        "schedule11_current_year_claim_used": schedule11_current_year_claim_used,
        "schedule11_current_year_unused": schedule11_current_year_unused,
        "schedule11_carryforward_claim_requested": schedule11_carryforward_claim_requested,
        "schedule11_carryforward_claim_used": schedule11_carryforward_claim_used,
        "schedule11_carryforward_unused": schedule11_carryforward_unused,
        "schedule11_total_claim_used": schedule11_total_claim_used,
        "schedule11_total_unused": schedule11_total_unused,
        "schedule11_transfer_from_spouse": schedule11_transfer_from_spouse,
        "t776_gross_rents": value(data, "t776_gross_rents"),
        "t776_advertising": value(data, "t776_advertising"),
        "t776_insurance": value(data, "t776_insurance"),
        "t776_interest_bank_charges": value(data, "t776_interest_bank_charges"),
        "t776_property_taxes": value(data, "t776_property_taxes"),
        "t776_utilities": value(data, "t776_utilities"),
        "t776_repairs_maintenance": value(data, "t776_repairs_maintenance"),
        "t776_management_admin": value(data, "t776_management_admin"),
        "t776_travel": value(data, "t776_travel"),
        "t776_office_expenses": value(data, "t776_office_expenses"),
        "t776_other_expenses": value(data, "t776_other_expenses"),
        "t776_total_expenses_before_cca": value(data, "t776_total_expenses_before_cca"),
        "t776_cca": value(data, "t776_cca"),
        "t776_net_rental_income_before_manual": value(data, "t776_net_rental_income_before_manual"),
        "manual_taxable_capital_gains": manual_taxable_capital_gains,
        "schedule3_proceeds_total": value(data, "schedule3_proceeds_total"),
        "schedule3_acb_total": value(data, "schedule3_acb_total"),
        "schedule3_outlays_total": value(data, "schedule3_outlays_total"),
        "schedule3_gross_capital_gains": value(data, "schedule3_gross_capital_gains"),
        "schedule3_gross_capital_losses": value(data, "schedule3_gross_capital_losses"),
        "schedule3_net_capital_gain_or_loss": value(data, "schedule3_net_capital_gain_or_loss"),
        "schedule3_taxable_capital_gains_before_manual": value(data, "schedule3_taxable_capital_gains_before_manual"),
        "schedule3_allowable_capital_loss": value(data, "schedule3_allowable_capital_loss"),
        "schedule3_t3_box21_amount": value(data, "schedule3_t3_box21_amount"),
        "schedule3_t4ps_box34_amount": value(data, "schedule3_t4ps_box34_amount"),
        "net_capital_loss_carryforward_requested": net_capital_loss_carryforward_requested,
        "net_capital_loss_carryforward": net_capital_loss_carryforward_used,
        "net_capital_loss_carryforward_unused": net_capital_loss_carryforward_unused,
        "other_loss_carryforward": value(data, "other_loss_carryforward"),
        "federal_basic_tax": federal_basic_tax,
        "federal_non_refundable_credits": federal_non_refundable_credits,
        "federal_dividend_tax_credit": federal_dividend_tax_credit,
        "federal_age_amount_auto": federal_age_amount_auto,
        "federal_medical_claim": federal_medical_claim,
        "donation_first_200": donation_credit["first_200"],
        "donation_amount_above_200": donation_credit["amount_above_200"],
        "donation_high_rate_portion": donation_credit["high_rate_portion"],
        "donation_remaining_29_portion": donation_credit["remaining_29_portion"],
        "schedule9_regular_limit": schedule9_regular_allocation["regular_limit"],
        "schedule9_current_year_donations_available": schedule9_current_year_donations_available,
        "schedule9_current_year_donations_claim_requested": schedule9_current_year_donations_claim_requested,
        "schedule9_current_year_donations_claim_used": schedule9_current_year_donations_claim_used,
        "schedule9_current_year_donations_unused": schedule9_current_year_donations_unused,
        "schedule9_carryforward_available": schedule9_carryforward_available,
        "schedule9_carryforward_claim_requested": schedule9_carryforward_claim_requested,
        "schedule9_carryforward_claim_used": schedule9_carryforward_claim_used,
        "schedule9_carryforward_unused": schedule9_carryforward_unused,
        "schedule9_total_regular_donations_claimed": schedule9_total_regular_donations_claimed,
        "schedule9_total_regular_donations_unused": schedule9_total_regular_donations_unused,
        "schedule9_unlimited_gifts_claimed": ecological_cultural_gifts,
        "federal_donation_credit": donation_credit["federal_credit"],
        "ontario_donation_credit": donation_credit["ontario_credit"],
        "provincial_donation_credit": provincial_donation_credit,
        "ab_supplemental_tax_credit": ab_supplemental_tax_credit,
        "nb_special_non_refundable_credits": nb_special_non_refundable_credits,
        "nl_special_non_refundable_credits": nl_special_non_refundable_credits,
        "auto_spouse_amount": auto_spouse_amount,
        "auto_eligible_dependant_amount": auto_eligible_dependant_amount,
        "manual_spouse_claim": manual_spouse_claim,
        "manual_eligible_dependant_claim": manual_eligible_dependant_claim,
        "effective_spouse_claim": effective_spouse_claim,
        "effective_eligible_dependant_claim": effective_eligible_dependant_claim,
        "caregiver_claim_target": caregiver_claim_target,
        "disability_transfer_source": disability_transfer_source,
        "requested_caregiver_claim": household_claims["caregiver_requested"],
        "available_caregiver_claim": household_claims["caregiver_available"],
        "unused_caregiver_claim": max(0.0, household_claims["caregiver_available"] - household_claims["caregiver_claim_amount"]),
        "requested_disability_transfer": value(data, "ontario_disability_transfer"),
        "available_disability_transfer": household_claims["disability_transfer_available"],
        "unused_disability_transfer": max(0.0, household_claims["disability_transfer_available"] - household_claims["disability_transfer_used"]),
        "requested_medical_dependants": household_claims["medical_dependants_requested"],
        "available_medical_dependants": household_claims["medical_dependants_available"],
        "unused_medical_dependants": max(0.0, household_claims["medical_dependants_available"] - household_claims["medical_dependants_used"]),
        "provincial_spouse_claim_manual_component": manual_spouse_claim,
        "provincial_spouse_claim_auto_component": auto_spouse_amount,
        "provincial_eligible_claim_manual_component": manual_eligible_dependant_claim,
        "provincial_eligible_claim_auto_component": auto_eligible_dependant_amount,
        "provincial_disability_base_component": value(data, "disability_amount_claim"),
        "provincial_disability_transfer_component": effective_disability_transfer,
        "provincial_caregiver_requested_component": household_claims["caregiver_requested"],
        "provincial_caregiver_available_component": household_claims["caregiver_available"],
        "provincial_medical_dependants_requested_component": household_claims["medical_dependants_requested"],
        "provincial_medical_dependants_available_component": household_claims["medical_dependants_available"],
        "provincial_spouse_household_reason": household_claims["spouse_reason"],
        "provincial_eligible_household_reason": household_claims["eligible_reason"],
        "provincial_caregiver_household_reason": household_claims["caregiver_reason"],
        "provincial_disability_household_reason": household_claims["disability_transfer_reason"],
        "household_spouse_allowed": 1.0 if household_claims["spouse_allowed"] else 0.0,
        "household_spouse_reason": household_claims["spouse_reason"],
        "household_eligible_dependant_allowed": 1.0 if household_claims["eligible_allowed"] else 0.0,
        "household_eligible_dependant_reason": household_claims["eligible_reason"],
        "household_caregiver_allowed": 1.0 if household_claims["caregiver_allowed"] else 0.0,
        "household_caregiver_reason": household_claims["caregiver_reason"],
        "household_disability_transfer_allowed": 1.0 if household_claims["disability_transfer_allowed"] else 0.0,
        "household_disability_transfer_reason": household_claims["disability_transfer_reason"],
        "household_disability_transfer_used": household_claims["disability_transfer_used"],
        "household_medical_dependants_allowed": 1.0 if household_claims["medical_dependants_allowed"] else 0.0,
        "household_medical_dependants_reason": household_claims["medical_dependants_reason"],
        "household_medical_dependants_used": household_claims["medical_dependants_used"],
        "household_qualifies_as_dependant_relative": 1.0 if household_claims["qualifies_as_dependant_relative"] else 0.0,
        "federal_foreign_tax_credit": federal_foreign_tax_credit,
        "t2209_foreign_income_ratio": t2209_foreign_income_ratio,
        "t2209_basic_federal_tax_used": t2209_basic_federal_tax,
        "t2209_limit_before_property_cap": t2209_limit_before_property_cap,
        "federal_foreign_tax_credit_limit": t2209_limit,
        "foreign_property_limit": foreign_property_limit,
        "t2209_non_business_tax_paid": t2209_non_business_tax_paid,
        "t2209_net_foreign_non_business_income": t2209_net_foreign_non_business_income,
        "t2209_net_income": t2209_net_income,
        "federal_tax": federal_tax,
        "provincial_basic_tax": provincial_basic_tax,
        "provincial_non_refundable_credits": provincial_non_refundable_credits,
        "provincial_basic_personal_credit": provincial_basic_personal_credit,
        "provincial_basic_personal_claim": provincial_basic_personal_claim,
        "provincial_cpp_ei_claim": provincial_cpp_ei_claim,
        "provincial_cpp_ei_credit": provincial_cpp_ei_credit,
        "provincial_age_claim": provincial_age_claim,
        "provincial_age_credit": provincial_age_credit,
        "provincial_pension_claim": provincial_pension_claim,
        "provincial_pension_credit": provincial_pension_credit,
        "provincial_spouse_claim": provincial_spouse_claim,
        "provincial_spouse_credit": provincial_spouse_credit,
        "provincial_eligible_dependant_claim": provincial_eligible_dependant_claim,
        "provincial_eligible_dependant_credit": provincial_eligible_dependant_credit,
        "provincial_disability_claim": provincial_disability_claim,
        "provincial_disability_credit": provincial_disability_credit,
        "provincial_caregiver_claim": provincial_caregiver_claim,
        "provincial_caregiver_credit": provincial_caregiver_credit,
        "provincial_medical_claim_base": provincial_medical_claim_base,
        "provincial_medical_credit": provincial_medical_credit,
        "provincial_medical_dependant_claim_base": provincial_medical_dependant_claim_base,
        "provincial_medical_dependant_credit": provincial_medical_dependant_credit,
        "provincial_student_claim": provincial_student_claim,
        "provincial_student_credit": provincial_student_credit,
        "provincial_adoption_claim": provincial_adoption_claim,
        "provincial_adoption_credit": provincial_adoption_credit,
        "provincial_additional_credit": provincial_additional_credit,
        "provincial_tax_after_non_refundable_credits": provincial_tax_after_non_refundable_credits,
        "provincial_tax_after_surtax": provincial_tax_after_surtax,
        "provincial_tax_after_dividend_credit": provincial_tax_after_dividend_credit,
        "provincial_tax_after_reduction": provincial_tax_after_reduction,
        "provincial_tax_after_foreign_tax_credit": provincial_tax_after_foreign_tax_credit,
        "provincial_tax_after_lift_credit": provincial_tax_after_lift_credit,
        "provincial_tax_before_health_premium": provincial_tax_before_health_premium,
        "ontario_age_amount_auto": provincial_age_amount_auto if province == "ON" else 0.0,
        "ontario_pension_amount": provincial_pension_amount if province == "ON" else 0.0,
        "ontario_medical_claim": provincial_medical_claim if province == "ON" else 0.0,
        "ontario_medical_dependant_claim": provincial_medical_dependant_claim if province == "ON" else 0.0,
        "ontario_child_reduction": ontario_child_reduction,
        "ontario_impairment_reduction": ontario_impairment_reduction,
        "ontario_dividend_tax_credit_auto": provincial_dividend_tax_credit_auto if province == "ON" else 0.0,
        "ontario_dividend_tax_credit": provincial_dividend_tax_credit if province == "ON" else 0.0,
        "provincial_age_amount_auto": provincial_age_amount_auto,
        "provincial_pension_amount": provincial_pension_amount,
        "provincial_medical_claim": provincial_medical_claim,
        "provincial_medical_dependant_claim": provincial_medical_dependant_claim,
        "provincial_dividend_tax_credit_auto": provincial_dividend_tax_credit_auto,
        "provincial_dividend_tax_credit": provincial_dividend_tax_credit,
        "provincial_tax_reduction": provincial_tax_reduction,
        "provincial_tax_reduction_max": provincial_tax_reduction_max,
        "provincial_tax_reduction_base": provincial_tax_reduction_base,
        "provincial_low_income_reduction": low_income_reduction["credit"],
        "provincial_caregiver_claim_amount": provincial_caregiver_claim_amount,
        "provincial_dependent_children_count": provincial_dependant_children_count,
        "provincial_foreign_tax_credit": provincial_foreign_tax_credit,
        "mb479_personal_tax_credit": mb479_personal_tax_credit,
        "mb479_homeowners_affordability_credit": mb479_homeowners_affordability_credit,
        "mb479_renters_affordability_credit": mb479_renters_affordability_credit,
        "mb479_seniors_school_rebate": mb479_seniors_school_rebate,
        "mb479_primary_caregiver_credit": mb479_primary_caregiver_credit,
        "mb479_fertility_credit": mb479_fertility_credit,
        "ns479_volunteer_credit": ns479_volunteer_credit,
        "ns479_childrens_sports_arts_credit": ns479_childrens_sports_arts_credit,
        "nb_political_contribution_credit": nb_political_contribution_credit,
        "nb_small_business_investor_credit": nb_small_business_investor_credit,
        "nb_lsvcc_credit": nb_lsvcc_credit,
        "nb_seniors_home_renovation_credit": nb_seniors_home_renovation_credit,
        "nl_political_contribution_credit": nl_political_contribution_credit,
        "nl_direct_equity_credit": nl_direct_equity_credit,
        "nl_resort_property_credit": nl_resort_property_credit,
        "nl_venture_capital_credit": nl_venture_capital_credit,
        "nl_unused_venture_capital_credit": nl_unused_venture_capital_credit,
        "nl479_other_refundable_credits": nl479_other_refundable_credits,
        "ontario_fertility_treatment_expenses": ontario_fertility_treatment_expenses,
        "ontario_fertility_credit": ontario_fertility_credit,
        "ontario_seniors_public_transit_expenses": ontario_seniors_public_transit_expenses,
        "ontario_seniors_transit_credit": ontario_seniors_transit_credit,
        "bc_renters_credit_eligible": float(bc_renters_credit_eligible),
        "bc_renters_credit_base": bc_renters_credit["base_credit"],
        "bc_renters_credit_phaseout": bc_renters_credit["phaseout"],
        "bc_renters_credit": bc_renters_credit["credit"],
        "bc_home_renovation_expenses": bc_home_renovation_expenses,
        "bc_home_renovation_eligible": float(bc_home_renovation_eligible),
        "bc_home_renovation_credit": bc_home_renovation_credit,
        "sk_fertility_treatment_expenses": sk_fertility_treatment_expenses,
        "sk_fertility_credit": sk_fertility_credit,
        "pe_volunteer_credit_eligible": float(pe_volunteer_credit_eligible),
        "pe_volunteer_credit": pe_volunteer_credit,
        "provincial_special_refundable_credits": provincial_special_refundable_credits,
        "federal_refundable_credits": federal_refundable_credits,
        "manual_provincial_refundable_credits": manual_provincial_refundable_credits,
        "other_manual_refundable_credits": other_manual_refundable_credits,
        "manual_refundable_credits_total": manual_refundable_credits_total,
        "canada_workers_benefit_manual": canada_workers_benefit,
        "canada_workers_benefit_auto": canada_workers_benefit_auto_total,
        "canada_workers_benefit_base_credit": auto_canada_workers_benefit["base_credit"],
        "canada_workers_benefit_phaseout": auto_canada_workers_benefit["phaseout"],
        "cwb_disability_supplement_eligible": float(cwb_disability_supplement_eligible),
        "spouse_cwb_disability_supplement_eligible": float(spouse_cwb_disability_supplement_eligible),
        "cwb_disability_supplement_auto": auto_cwb_disability_supplement["credit"],
        "cwb_disability_supplement_base_credit": auto_cwb_disability_supplement["base_credit"],
        "cwb_disability_supplement_phaseout": auto_cwb_disability_supplement["phaseout"],
        "canada_workers_benefit": canada_workers_benefit_used,
        "canada_training_credit_limit_available": canada_training_credit_limit_available,
        "canada_training_credit_manual": canada_training_credit,
        "canada_training_credit_auto": auto_canada_training_credit,
        "canada_training_credit": canada_training_credit_used,
        "medical_expense_supplement_manual": medical_expense_supplement,
        "medical_expense_supplement_auto": auto_medical_expense_supplement["credit"],
        "medical_expense_supplement_base_credit": auto_medical_expense_supplement["base_credit"],
        "medical_expense_supplement_phaseout": auto_medical_expense_supplement["phaseout"],
        "medical_expense_supplement": medical_expense_supplement_used,
        "cpp_withheld_total": cpp_withheld_total,
        "ei_withheld_total": ei_withheld_total,
        "cpp_overpayment_refund": payroll_overpayment_refunds["cpp_overpayment"],
        "ei_overpayment_refund": payroll_overpayment_refunds["ei_overpayment"],
        "payroll_overpayment_refund_total": payroll_overpayment_refunds["total_refund"],
        "other_federal_refundable_credits": other_federal_refundable_credits,
        "t2036_line1": t2036_line1,
        "t2036_foreign_income_ratio": t2036_foreign_income_ratio,
        "t2036_limit": t2036_limit,
        "t2036_unused_foreign_tax": t2036_unused_foreign_tax,
        "provincial_tax_otherwise_payable": provincial_tax_otherwise_payable,
        "lift_max_credit": lift_credit["max_credit"],
        "lift_reduction_base": lift_credit.get("reduction_base", 0.0),
        "lift_credit": lift_credit["credit"],
        "provincial_surtax": provincial_surtax,
        "provincial_health_premium": provincial_health_premium,
        "provincial_tax": provincial_tax,
        "taxable_eligible_dividends": taxable_eligible_dividends,
        "taxable_non_eligible_dividends": taxable_non_eligible_dividends,
        "employee_cpp": employee_payroll["employee_cpp_total"],
        "cpp_deduction": cpp_deduction,
        "cpp_credit_base": cpp_credit_base,
        "total_cpp": total_cpp,
        "ei": ei,
        "total_payable": total_payable,
        "income_tax_withheld": income_tax_withheld,
        "installments_paid": installments_paid,
        "other_payments": other_payments,
        "t4ps_box41_epsp_contributions": value(data, "t4ps_box41_epsp_contributions"),
        "refundable_credits": refundable_credits,
        "total_payments": total_payments,
        "refund_or_balance": refund_or_balance,
        "line_48400_refund": max(0.0, refund_or_balance),
        "line_48500_balance_owing": max(0.0, -refund_or_balance),
    }
