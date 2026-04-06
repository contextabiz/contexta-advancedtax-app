import pandas as pd

PROVINCIAL_FORM_CODES = {
    "AB": "AB428",
    "BC": "BC428",
    "MB": "MB428",
    "NB": "NB428",
    "NL": "NL428",
    "NS": "NS428",
    "ON": "ON428",
    "PE": "PE428",
    "SK": "SK428",
}


def build_provincial_worksheet_df(result: dict, province_code: str, province_name: str) -> pd.DataFrame:
    form_code = PROVINCIAL_FORM_CODES.get(province_code, "428")
    if province_code == "ON":
        rows = [
            {"Line": "1", "Description": "Taxable income", "Amount": result["taxable_income"]},
            {"Line": "5", "Description": "Ontario tax on taxable income", "Amount": result["provincial_basic_tax"]},
            {"Line": "6", "Description": "Ontario basic personal amount claim", "Amount": result.get("provincial_basic_personal_claim", 0.0)},
            {"Line": "6C", "Description": "Ontario basic personal credit", "Amount": result.get("provincial_basic_personal_credit", 0.0)},
            {"Line": "7", "Description": "Ontario CPP/EI claim base", "Amount": result.get("provincial_cpp_ei_claim", 0.0)},
            {"Line": "7C", "Description": "Ontario CPP/EI credit", "Amount": result.get("provincial_cpp_ei_credit", 0.0)},
            {"Line": "19", "Description": "Ontario age claim amount", "Amount": result.get("provincial_age_claim", 0.0)},
            {"Line": "19C", "Description": "Ontario age credit", "Amount": result.get("provincial_age_credit", 0.0)},
            {"Line": "24", "Description": "Ontario pension claim amount", "Amount": result.get("provincial_pension_claim", 0.0)},
            {"Line": "24C", "Description": "Ontario pension credit", "Amount": result.get("provincial_pension_credit", 0.0)},
            {"Line": "25A", "Description": "Ontario spouse manual claim entered", "Amount": result.get("provincial_spouse_claim_manual_component", 0.0)},
            {"Line": "25B", "Description": "Ontario spouse auto amount from household rules", "Amount": result.get("provincial_spouse_claim_auto_component", 0.0)},
            {"Line": "25", "Description": "Ontario spouse claim amount", "Amount": result.get("provincial_spouse_claim", 0.0)},
            {"Line": "25C", "Description": "Ontario spouse credit", "Amount": result.get("provincial_spouse_credit", 0.0)},
            {"Line": "26A", "Description": "Ontario eligible dependant manual claim entered", "Amount": result.get("provincial_eligible_claim_manual_component", 0.0)},
            {"Line": "26B", "Description": "Ontario eligible dependant auto amount from household rules", "Amount": result.get("provincial_eligible_claim_auto_component", 0.0)},
            {"Line": "26", "Description": "Ontario eligible dependant claim amount", "Amount": result.get("provincial_eligible_dependant_claim", 0.0)},
            {"Line": "26C", "Description": "Ontario eligible dependant credit", "Amount": result.get("provincial_eligible_dependant_credit", 0.0)},
            {"Line": "27A", "Description": "Ontario disability base claim entered", "Amount": result.get("provincial_disability_base_component", 0.0)},
            {"Line": "27B", "Description": "Ontario disability transfer portion used", "Amount": result.get("provincial_disability_transfer_component", 0.0)},
            {"Line": "27", "Description": "Ontario disability claim amount", "Amount": result.get("provincial_disability_claim", 0.0)},
            {"Line": "27C", "Description": "Ontario disability credit", "Amount": result.get("provincial_disability_credit", 0.0)},
            {"Line": "28A", "Description": "Ontario caregiver amount requested", "Amount": result.get("provincial_caregiver_requested_component", 0.0)},
            {"Line": "28B", "Description": "Ontario caregiver amount available after household checks", "Amount": result.get("provincial_caregiver_available_component", 0.0)},
            {"Line": "28", "Description": "Ontario caregiver claim amount", "Amount": result.get("provincial_caregiver_claim", 0.0)},
            {"Line": "28C", "Description": "Ontario caregiver credit", "Amount": result.get("provincial_caregiver_credit", 0.0)},
            {"Line": "31", "Description": "Ontario medical claim amount", "Amount": result.get("provincial_medical_claim_base", 0.0)},
            {"Line": "31C", "Description": "Ontario medical credit", "Amount": result.get("provincial_medical_credit", 0.0)},
            {"Line": "32A", "Description": "Ontario dependant medical amount requested", "Amount": result.get("provincial_medical_dependants_requested_component", 0.0)},
            {"Line": "32B", "Description": "Ontario dependant medical amount available after household checks", "Amount": result.get("provincial_medical_dependants_available_component", 0.0)},
            {"Line": "32", "Description": "Ontario medical dependant claim amount", "Amount": result.get("provincial_medical_dependant_claim_base", 0.0)},
            {"Line": "32C", "Description": "Ontario medical dependant credit", "Amount": result.get("provincial_medical_dependant_credit", 0.0)},
            {"Line": "33", "Description": "Ontario student/tuition claim amount", "Amount": result.get("provincial_student_claim", 0.0)},
            {"Line": "33C", "Description": "Ontario student/tuition credit", "Amount": result.get("provincial_student_credit", 0.0)},
            {"Line": "34", "Description": "Ontario adoption claim amount", "Amount": result.get("provincial_adoption_claim", 0.0)},
            {"Line": "34C", "Description": "Ontario adoption credit", "Amount": result.get("provincial_adoption_credit", 0.0)},
            {"Line": "46", "Description": "Ontario donation claim result", "Amount": result.get("donation_amount_above_200", 0.0) + result.get("donation_first_200", 0.0)},
            {"Line": "46C", "Description": "Ontario donation credit", "Amount": result.get("provincial_donation_credit", 0.0)},
            {"Line": "46A", "Description": "Additional Ontario credit amount", "Amount": result.get("provincial_additional_credit", 0.0)},
            {"Line": "47", "Description": "Ontario non-refundable tax credits", "Amount": result["provincial_non_refundable_credits"]},
            {"Line": "49", "Description": "Tax after non-refundable credits", "Amount": result.get("provincial_tax_after_non_refundable_credits", 0.0)},
            {"Line": "52", "Description": "Ontario surtax", "Amount": result.get("provincial_surtax", 0.0)},
            {"Line": "53", "Description": "Tax after surtax", "Amount": result.get("provincial_tax_after_surtax", 0.0)},
            {"Line": "57", "Description": "Ontario dividend tax credit", "Amount": result.get("provincial_dividend_tax_credit", 0.0)},
            {"Line": "58", "Description": "Tax after dividend tax credit", "Amount": result.get("provincial_tax_after_dividend_credit", 0.0)},
            {"Line": "60", "Description": "Ontario tax reduction", "Amount": result.get("provincial_tax_reduction", 0.0)},
            {"Line": "61", "Description": "Tax after reduction", "Amount": result.get("provincial_tax_after_reduction", 0.0)},
            {"Line": "69", "Description": "Ontario foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
            {"Line": "70", "Description": "Tax after foreign tax credit", "Amount": result.get("provincial_tax_after_foreign_tax_credit", 0.0)},
            {"Line": "70A", "Description": "Ontario LIFT credit", "Amount": result.get("lift_credit", 0.0)},
            {"Line": "70B", "Description": "Tax after LIFT credit", "Amount": result.get("provincial_tax_after_lift_credit", 0.0)},
            {"Line": "71", "Description": "Ontario health premium", "Amount": result.get("provincial_health_premium", 0.0)},
            {"Line": "72", "Description": "Ontario tax", "Amount": result["provincial_tax"]},
        ]
        df = pd.DataFrame(rows)
        df["Form"] = form_code
        return df[["Form", "Line", "Description", "Amount"]]
    if province_code == "BC":
        rows = [
            {"Line": "1", "Description": "Taxable income", "Amount": result["taxable_income"]},
            {"Line": "5", "Description": "British Columbia tax on taxable income", "Amount": result["provincial_basic_tax"]},
            {"Line": "6", "Description": "B.C. basic personal amount claim", "Amount": result.get("provincial_basic_personal_claim", 0.0)},
            {"Line": "6C", "Description": "B.C. basic personal credit", "Amount": result.get("provincial_basic_personal_credit", 0.0)},
            {"Line": "7", "Description": "B.C. CPP/EI claim base", "Amount": result.get("provincial_cpp_ei_claim", 0.0)},
            {"Line": "7C", "Description": "B.C. CPP/EI credit", "Amount": result.get("provincial_cpp_ei_credit", 0.0)},
            {"Line": "12", "Description": "B.C. age claim amount", "Amount": result.get("provincial_age_claim", 0.0)},
            {"Line": "12C", "Description": "B.C. age credit", "Amount": result.get("provincial_age_credit", 0.0)},
            {"Line": "16", "Description": "B.C. pension claim amount", "Amount": result.get("provincial_pension_claim", 0.0)},
            {"Line": "16C", "Description": "B.C. pension credit", "Amount": result.get("provincial_pension_credit", 0.0)},
            {"Line": "17A", "Description": "B.C. spouse manual claim entered", "Amount": result.get("provincial_spouse_claim_manual_component", 0.0)},
            {"Line": "17B", "Description": "B.C. spouse auto amount from household rules", "Amount": result.get("provincial_spouse_claim_auto_component", 0.0)},
            {"Line": "17", "Description": "B.C. spouse claim amount", "Amount": result.get("provincial_spouse_claim", 0.0)},
            {"Line": "17C", "Description": "B.C. spouse credit", "Amount": result.get("provincial_spouse_credit", 0.0)},
            {"Line": "18A", "Description": "B.C. eligible dependant manual claim entered", "Amount": result.get("provincial_eligible_claim_manual_component", 0.0)},
            {"Line": "18B", "Description": "B.C. eligible dependant auto amount from household rules", "Amount": result.get("provincial_eligible_claim_auto_component", 0.0)},
            {"Line": "18", "Description": "B.C. eligible dependant claim amount", "Amount": result.get("provincial_eligible_dependant_claim", 0.0)},
            {"Line": "18C", "Description": "B.C. eligible dependant credit", "Amount": result.get("provincial_eligible_dependant_credit", 0.0)},
            {"Line": "19A", "Description": "B.C. disability base claim entered", "Amount": result.get("provincial_disability_base_component", 0.0)},
            {"Line": "19B", "Description": "B.C. disability transfer portion used", "Amount": result.get("provincial_disability_transfer_component", 0.0)},
            {"Line": "19", "Description": "B.C. disability claim amount", "Amount": result.get("provincial_disability_claim", 0.0)},
            {"Line": "19C", "Description": "B.C. disability credit", "Amount": result.get("provincial_disability_credit", 0.0)},
            {"Line": "20A", "Description": "B.C. caregiver amount requested", "Amount": result.get("provincial_caregiver_requested_component", 0.0)},
            {"Line": "20B", "Description": "B.C. caregiver amount available after household checks", "Amount": result.get("provincial_caregiver_available_component", 0.0)},
            {"Line": "20", "Description": "B.C. caregiver claim amount", "Amount": result.get("provincial_caregiver_claim", 0.0)},
            {"Line": "20C", "Description": "B.C. caregiver credit", "Amount": result.get("provincial_caregiver_credit", 0.0)},
            {"Line": "21", "Description": "B.C. medical claim amount", "Amount": result.get("provincial_medical_claim_base", 0.0)},
            {"Line": "21C", "Description": "B.C. medical credit", "Amount": result.get("provincial_medical_credit", 0.0)},
            {"Line": "29", "Description": "B.C. donation claim result", "Amount": result.get("donation_amount_above_200", 0.0) + result.get("donation_first_200", 0.0)},
            {"Line": "29C", "Description": "B.C. donation credit", "Amount": result.get("provincial_donation_credit", 0.0)},
            {"Line": "30", "Description": "Additional B.C. credit amount", "Amount": result.get("provincial_additional_credit", 0.0)},
            {"Line": "31", "Description": "B.C. non-refundable tax credits", "Amount": result["provincial_non_refundable_credits"]},
            {"Line": "37", "Description": "Tax after non-refundable credits", "Amount": result.get("provincial_tax_after_non_refundable_credits", 0.0)},
            {"Line": "61", "Description": "B.C. dividend tax credit", "Amount": result.get("provincial_dividend_tax_credit", 0.0)},
            {"Line": "62", "Description": "Tax after dividend tax credit", "Amount": result.get("provincial_tax_after_dividend_credit", 0.0)},
            {"Line": "79", "Description": "B.C. tax reduction", "Amount": result.get("provincial_tax_reduction", 0.0)},
            {"Line": "80", "Description": "B.C. tax reduction net-income excess", "Amount": result.get("provincial_tax_reduction_base", 0.0)},
            {"Line": "81", "Description": "Tax after reduction", "Amount": result.get("provincial_tax_after_reduction", 0.0)},
            {"Line": "83", "Description": "B.C. foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
            {"Line": "84", "Description": "Tax after foreign tax credit", "Amount": result.get("provincial_tax_after_foreign_tax_credit", 0.0)},
            {"Line": "91", "Description": "British Columbia tax", "Amount": result["provincial_tax"]},
        ]
        df = pd.DataFrame(rows)
        df["Form"] = form_code
        return df[["Form", "Line", "Description", "Amount"]]
    if province_code == "AB":
        rows = [
            {"Line": "1", "Description": "Taxable income", "Amount": result["taxable_income"]},
            {"Line": "5", "Description": "Alberta tax on taxable income", "Amount": result["provincial_basic_tax"]},
            {"Line": "6", "Description": "Alberta basic personal amount claim", "Amount": result.get("provincial_basic_personal_claim", 0.0)},
            {"Line": "6C", "Description": "Alberta basic personal credit", "Amount": result.get("provincial_basic_personal_credit", 0.0)},
            {"Line": "7", "Description": "Alberta CPP/EI claim base", "Amount": result.get("provincial_cpp_ei_claim", 0.0)},
            {"Line": "7C", "Description": "Alberta CPP/EI credit", "Amount": result.get("provincial_cpp_ei_credit", 0.0)},
            {"Line": "8A", "Description": "Alberta spouse manual claim entered", "Amount": result.get("provincial_spouse_claim_manual_component", 0.0)},
            {"Line": "8B", "Description": "Alberta spouse auto amount from household rules", "Amount": result.get("provincial_spouse_claim_auto_component", 0.0)},
            {"Line": "8", "Description": "Alberta spouse claim amount", "Amount": result.get("provincial_spouse_claim", 0.0)},
            {"Line": "8C", "Description": "Alberta spouse credit", "Amount": result.get("provincial_spouse_credit", 0.0)},
            {"Line": "9A", "Description": "Alberta eligible dependant manual claim entered", "Amount": result.get("provincial_eligible_claim_manual_component", 0.0)},
            {"Line": "9B", "Description": "Alberta eligible dependant auto amount from household rules", "Amount": result.get("provincial_eligible_claim_auto_component", 0.0)},
            {"Line": "9", "Description": "Alberta eligible dependant claim amount", "Amount": result.get("provincial_eligible_dependant_claim", 0.0)},
            {"Line": "9C", "Description": "Alberta eligible dependant credit", "Amount": result.get("provincial_eligible_dependant_credit", 0.0)},
            {"Line": "10A", "Description": "Alberta caregiver amount requested", "Amount": result.get("provincial_caregiver_requested_component", 0.0)},
            {"Line": "10B", "Description": "Alberta caregiver amount available after household checks", "Amount": result.get("provincial_caregiver_available_component", 0.0)},
            {"Line": "10", "Description": "Alberta caregiver claim amount", "Amount": result.get("provincial_caregiver_claim", 0.0)},
            {"Line": "10C", "Description": "Alberta caregiver credit", "Amount": result.get("provincial_caregiver_credit", 0.0)},
            {"Line": "12", "Description": "Alberta pension claim amount", "Amount": result.get("provincial_pension_claim", 0.0)},
            {"Line": "12C", "Description": "Alberta pension credit", "Amount": result.get("provincial_pension_credit", 0.0)},
            {"Line": "13A", "Description": "Alberta disability base claim entered", "Amount": result.get("provincial_disability_base_component", 0.0)},
            {"Line": "13B", "Description": "Alberta disability transfer portion used", "Amount": result.get("provincial_disability_transfer_component", 0.0)},
            {"Line": "13", "Description": "Alberta disability claim amount", "Amount": result.get("provincial_disability_claim", 0.0)},
            {"Line": "13C", "Description": "Alberta disability credit", "Amount": result.get("provincial_disability_credit", 0.0)},
            {"Line": "18", "Description": "Alberta medical claim amount", "Amount": result.get("provincial_medical_claim_base", 0.0)},
            {"Line": "18C", "Description": "Alberta medical credit", "Amount": result.get("provincial_medical_credit", 0.0)},
            {"Line": "30", "Description": "Alberta donation claim result", "Amount": result.get("donation_amount_above_200", 0.0) + result.get("donation_first_200", 0.0)},
            {"Line": "30C", "Description": "Alberta donation credit", "Amount": result.get("provincial_donation_credit", 0.0)},
            {"Line": "31", "Description": "Additional Alberta credit amount", "Amount": result.get("provincial_additional_credit", 0.0)},
            {"Line": "31A", "Description": "Alberta supplemental household base component", "Amount": result.get("provincial_spouse_claim", 0.0) + result.get("provincial_eligible_dependant_claim", 0.0) + result.get("provincial_caregiver_claim", 0.0) + result.get("provincial_disability_claim", 0.0)},
            {"Line": "42", "Description": "Alberta non-refundable tax credits", "Amount": result["provincial_non_refundable_credits"]},
            {"Line": "43", "Description": "Tax after non-refundable credits", "Amount": result.get("provincial_tax_after_non_refundable_credits", 0.0)},
            {"Line": "49", "Description": "Alberta foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
            {"Line": "50", "Description": "Tax after foreign tax credit", "Amount": result.get("provincial_tax_after_foreign_tax_credit", 0.0)},
            {"Line": "61545", "Description": "Alberta supplemental tax credit", "Amount": result.get("ab_supplemental_tax_credit", 0.0)},
            {"Line": "73", "Description": "Alberta tax", "Amount": result["provincial_tax"]},
        ]
        df = pd.DataFrame(rows)
        df["Form"] = form_code
        return df[["Form", "Line", "Description", "Amount"]]
    rows = [
        {"Line": "50", "Description": f"{province_name} non-refundable tax credits", "Amount": result["provincial_non_refundable_credits"]},
        {"Line": "Age", "Description": f"{province_name} age amount used", "Amount": result.get("provincial_age_amount_auto", 0.0)},
        {"Line": "Pension", "Description": f"{province_name} pension amount used", "Amount": result.get("provincial_pension_amount", 0.0)},
        {"Line": "Caregiver", "Description": f"{province_name} caregiver amount base used", "Amount": result.get("provincial_caregiver_claim_amount", 0.0)},
        {"Line": "Medical", "Description": f"{province_name} medical claim used", "Amount": result.get("provincial_medical_claim", 0.0)},
        {"Line": "Donation", "Description": f"{province_name} donation credit", "Amount": result.get("provincial_donation_credit", 0.0)},
        {"Line": "Dividend", "Description": f"{province_name} dividend tax credit", "Amount": result.get("provincial_dividend_tax_credit", 0.0)},
        {"Line": "Low-income", "Description": f"{province_name} low-income reduction", "Amount": result.get("provincial_low_income_reduction", 0.0)},
        {"Line": "Reduction", "Description": f"{province_name} tax reduction / low-income credit", "Amount": result.get("provincial_tax_reduction", 0.0)},
        {"Line": "82", "Description": "Provincial foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
        {"Line": "Surtax", "Description": f"{province_name} surtax", "Amount": result.get("provincial_surtax", 0.0)},
        {"Line": "Premium", "Description": f"{province_name} health premium", "Amount": result.get("provincial_health_premium", 0.0)},
        {"Line": "42800", "Description": f"{province_name} tax", "Amount": result["provincial_tax"]},
    ]
    if province_code == "ON":
        rows.insert(6, {"Line": "85", "Description": "Ontario LIFT credit", "Amount": result.get("lift_credit", 0.0)})
    if province_code == "BC":
        rows.insert(7, {"Line": "BC Reduction Base", "Description": "B.C. tax reduction net-income excess", "Amount": result.get("provincial_tax_reduction_base", 0.0)})
    if province_code == "AB":
        rows.insert(7, {"Line": "61545", "Description": "Alberta supplemental tax credit", "Amount": result.get("ab_supplemental_tax_credit", 0.0)})
    df = pd.DataFrame(rows)
    df["Form"] = form_code
    return df[["Form", "Line", "Description", "Amount"]]


def build_schedule_3_df(result: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Line": "Schedule", "Description": "Proceeds of disposition", "Amount": result.get("schedule3_proceeds_total", 0.0)},
            {"Line": "Schedule", "Description": "Adjusted cost base", "Amount": result.get("schedule3_acb_total", 0.0)},
            {"Line": "Schedule", "Description": "Outlays and expenses", "Amount": result.get("schedule3_outlays_total", 0.0)},
            {"Line": "Schedule", "Description": "Gross capital gains", "Amount": result.get("schedule3_gross_capital_gains", 0.0)},
            {"Line": "Schedule", "Description": "Gross capital losses", "Amount": result.get("schedule3_gross_capital_losses", 0.0)},
            {"Line": "Schedule", "Description": "Net capital gain/loss before inclusion", "Amount": result.get("schedule3_net_capital_gain_or_loss", 0.0)},
            {"Line": "T3", "Description": "T3 box 21 capital gains amount", "Amount": result.get("schedule3_t3_box21_amount", 0.0)},
            {"Line": "T4PS", "Description": "T4PS box 34 capital gain/loss amount", "Amount": result.get("schedule3_t4ps_box34_amount", 0.0)},
            {"Line": "12700A", "Description": "Taxable capital gains from Schedule 3/T4PS", "Amount": result.get("schedule3_taxable_capital_gains_before_manual", 0.0)},
            {"Line": "12700B", "Description": "Manual additional taxable capital gains", "Amount": result.get("manual_taxable_capital_gains", 0.0)},
            {"Line": "12700", "Description": "Total taxable capital gains", "Amount": result.get("line_taxable_capital_gains", 0.0)},
            {"Line": "25300R", "Description": "Requested net capital loss carryforward", "Amount": result.get("net_capital_loss_carryforward_requested", 0.0)},
            {"Line": "25300", "Description": "Net capital loss carryforward used", "Amount": result.get("net_capital_loss_carryforward", 0.0)},
            {"Line": "25300U", "Description": "Requested carryforward not used", "Amount": result.get("net_capital_loss_carryforward_unused", 0.0)},
            {"Line": "Loss", "Description": "Current-year allowable capital loss", "Amount": result.get("schedule3_allowable_capital_loss", 0.0)},
        ]
    )


def build_t776_df(result: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Line": "T776", "Description": "Gross rents", "Amount": result.get("t776_gross_rents", 0.0)},
            {"Line": "T776", "Description": "Advertising", "Amount": result.get("t776_advertising", 0.0)},
            {"Line": "T776", "Description": "Insurance", "Amount": result.get("t776_insurance", 0.0)},
            {"Line": "T776", "Description": "Interest and bank charges", "Amount": result.get("t776_interest_bank_charges", 0.0)},
            {"Line": "T776", "Description": "Property taxes", "Amount": result.get("t776_property_taxes", 0.0)},
            {"Line": "T776", "Description": "Utilities", "Amount": result.get("t776_utilities", 0.0)},
            {"Line": "T776", "Description": "Repairs and maintenance", "Amount": result.get("t776_repairs_maintenance", 0.0)},
            {"Line": "T776", "Description": "Management and administration", "Amount": result.get("t776_management_admin", 0.0)},
            {"Line": "T776", "Description": "Travel", "Amount": result.get("t776_travel", 0.0)},
            {"Line": "T776", "Description": "Office expenses", "Amount": result.get("t776_office_expenses", 0.0)},
            {"Line": "T776", "Description": "Other expenses", "Amount": result.get("t776_other_expenses", 0.0)},
            {"Line": "T776", "Description": "Total rental expenses before CCA", "Amount": result.get("t776_total_expenses_before_cca", 0.0)},
            {"Line": "T776", "Description": "CCA", "Amount": result.get("t776_cca", 0.0)},
            {"Line": "T776A", "Description": "Net rental income from T776 properties", "Amount": result.get("t776_net_rental_income_before_manual", 0.0)},
            {"Line": "12600A", "Description": "Manual additional net rental income", "Amount": result.get("manual_net_rental_income", 0.0)},
            {"Line": "12600", "Description": "Total net rental income", "Amount": result.get("line_rental_income", 0.0)},
        ]
    )


def build_schedule_11_df(result: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Line": "1", "Description": "Current-year T2202 tuition available", "Amount": result.get("schedule11_current_year_tuition_available", 0.0)},
            {"Line": "4", "Description": "Canada training credit maximum available", "Amount": result.get("schedule11_training_credit_max", 0.0)},
            {"Line": "5", "Description": "Canada training credit used", "Amount": result.get("canada_training_credit", 0.0)},
            {"Line": "6", "Description": "Current-year tuition left after training credit", "Amount": result.get("schedule11_current_year_available_after_training", 0.0)},
            {"Line": "9", "Description": "Prior-year tuition carryforward available", "Amount": result.get("schedule11_carryforward_available", 0.0)},
            {"Line": "10", "Description": "Total tuition available for 2025", "Amount": result.get("schedule11_total_available", 0.0)},
            {"Line": "11", "Description": "Federal tax base used for Schedule 11 room", "Amount": result.get("schedule11_line11_base", 0.0)},
            {"Line": "12", "Description": "Other federal credits base used before tuition", "Amount": result.get("schedule11_line12_other_credit_base", 0.0)},
            {"Line": "13", "Description": "Maximum federal tuition room before carryforward", "Amount": result.get("schedule11_line13_claim_room", 0.0)},
            {"Line": "14", "Description": "Carryforward claim used", "Amount": result.get("schedule11_carryforward_claim_used", 0.0)},
            {"Line": "15", "Description": "Remaining room after carryforward", "Amount": result.get("schedule11_line15_room_after_carryforward", 0.0)},
            {"Line": "16", "Description": "Current-year tuition claim used", "Amount": result.get("schedule11_current_year_claim_used", 0.0)},
            {"Line": "17 / 32300", "Description": "Federal tuition amount claimed", "Amount": result.get("schedule11_total_claim_used", 0.0)},
            {"Line": "Transfer-In", "Description": "Tuition transfer from spouse/partner", "Amount": result.get("schedule11_transfer_from_spouse", 0.0)},
            {"Line": "Unused-CY", "Description": "Unused current-year tuition remaining", "Amount": result.get("schedule11_current_year_unused", 0.0)},
            {"Line": "Unused-CF", "Description": "Unused carryforward remaining", "Amount": result.get("schedule11_carryforward_unused", 0.0)},
            {"Line": "Unused-Total", "Description": "Unused tuition remaining after claim", "Amount": result.get("schedule11_total_unused", 0.0)},
        ]
    )


def build_federal_net_tax_build_up_df(result: dict) -> pd.DataFrame:
    split_income_tax = 0.0
    investment_tax_credit = 0.0
    total_federal_credits = (
        result.get("federal_non_refundable_credits", 0.0)
        + result.get("federal_foreign_tax_credit", 0.0)
        + investment_tax_credit
    )
    return pd.DataFrame(
        [
            {"Line": "119 / 40424", "Description": "Federal tax on taxable income", "Amount": result.get("federal_basic_tax", 0.0)},
            {"Line": "120 / 40400", "Description": "Federal tax on split income", "Amount": split_income_tax},
            {"Line": "121", "Description": "Federal tax before credits", "Amount": result.get("federal_basic_tax", 0.0) + split_income_tax},
            {"Line": "122 / 35000", "Description": "Federal non-refundable tax credits", "Amount": result.get("federal_non_refundable_credits", 0.0)},
            {"Line": "123 / 40500", "Description": "Federal foreign tax credit", "Amount": result.get("federal_foreign_tax_credit", 0.0)},
            {"Line": "124 / 40427", "Description": "Federal investment tax credit", "Amount": investment_tax_credit},
            {"Line": "125", "Description": "Total federal credits claimed", "Amount": total_federal_credits},
            {"Line": "42000", "Description": "Net federal tax", "Amount": result.get("federal_tax", 0.0)},
        ]
    )


def build_on428_part_c_df(result: dict) -> pd.DataFrame:
    line74_basic_reduction = 294.0
    line75_child_reduction = result.get("ontario_child_reduction", 0.0)
    line76_impairment_reduction = result.get("ontario_impairment_reduction", 0.0)
    line77_total_reduction_base = line74_basic_reduction + line75_child_reduction + line76_impairment_reduction
    line78_doubled_reduction = line77_total_reduction_base * 2.0
    line79_tax_before_reduction = result.get("provincial_tax_after_dividend_credit", 0.0)
    line80_ontario_tax_reduction = result.get("provincial_tax_reduction", 0.0)
    line81_tax_after_reduction = result.get("provincial_tax_after_reduction", 0.0)
    line82_provincial_foreign_tax_credit = result.get("provincial_foreign_tax_credit", 0.0)
    line83_tax_after_foreign_tax_credit = result.get("provincial_tax_after_foreign_tax_credit", 0.0)
    line84_amount_before_lift = line83_tax_after_foreign_tax_credit
    line85_lift = result.get("lift_credit", 0.0)
    line86_tax_after_lift = result.get("provincial_tax_after_lift_credit", 0.0)
    line87_food_donation_credit = 0.0
    line88_tax_before_health_premium = line86_tax_after_lift - line87_food_donation_credit
    line89_health_premium = result.get("provincial_health_premium", 0.0)
    line90_final_ontario_tax = result.get("provincial_tax", 0.0)
    return pd.DataFrame(
        [
            {"Line": "74", "Description": "Basic reduction", "Amount": line74_basic_reduction},
            {"Line": "75", "Description": "Reduction for dependent children", "Amount": line75_child_reduction},
            {"Line": "76", "Description": "Reduction for dependants with impairment", "Amount": line76_impairment_reduction},
            {"Line": "77", "Description": "Total reduction base", "Amount": line77_total_reduction_base},
            {"Line": "78", "Description": "Line 77 multiplied by 2", "Amount": line78_doubled_reduction},
            {"Line": "79", "Description": "Tax before Ontario tax reduction", "Amount": line79_tax_before_reduction},
            {"Line": "80", "Description": "Ontario tax reduction", "Amount": line80_ontario_tax_reduction},
            {"Line": "81", "Description": "Tax after reduction", "Amount": line81_tax_after_reduction},
            {"Line": "82", "Description": "Provincial foreign tax credit", "Amount": line82_provincial_foreign_tax_credit},
            {"Line": "83", "Description": "Tax after provincial foreign tax credit", "Amount": line83_tax_after_foreign_tax_credit},
            {"Line": "84", "Description": "Amount before LIFT", "Amount": line84_amount_before_lift},
            {"Line": "85", "Description": "LIFT credit", "Amount": line85_lift},
            {"Line": "86", "Description": "Tax after LIFT", "Amount": line86_tax_after_lift},
            {"Line": "87", "Description": "Community food donation credit for farmers", "Amount": line87_food_donation_credit},
            {"Line": "88", "Description": "Tax before health premium", "Amount": line88_tax_before_health_premium},
            {"Line": "89", "Description": "Ontario health premium", "Amount": line89_health_premium},
            {"Line": "90 / 42800", "Description": "Ontario tax", "Amount": line90_final_ontario_tax},
        ]
    )


def build_on428a_lift_df(result: dict) -> pd.DataFrame:
    working_income = result.get("line_10100", 0.0)
    line2_employment_based_credit = working_income * 0.0505
    line3_max_allowable_credit = result.get("lift_max_credit", 0.0)
    adjusted_net_income = result.get("adjusted_net_income_for_lift", 0.0)
    spouse_adjusted_net_income = result.get("spouse_adjusted_net_income_for_lift", 0.0)
    single_threshold = 32500.0
    family_threshold = 65000.0
    single_excess = max(0.0, adjusted_net_income - single_threshold)
    family_net_income = adjusted_net_income + spouse_adjusted_net_income
    family_excess = max(0.0, family_net_income - family_threshold)
    reduction_base = result.get("lift_reduction_base", 0.0)
    line11_phaseout_reduction = reduction_base * 0.05
    return pd.DataFrame(
        [
            {"Line": "1", "Description": "Employment income used", "Amount": working_income},
            {"Line": "2", "Description": "Employment income multiplied by 5.05%", "Amount": line2_employment_based_credit},
            {"Line": "3", "Description": "Maximum allowable credit", "Amount": line3_max_allowable_credit},
            {"Line": "4", "Description": "Adjusted net income", "Amount": adjusted_net_income},
            {"Line": "5", "Description": "Single threshold", "Amount": single_threshold},
            {"Line": "6", "Description": "Single-income excess", "Amount": single_excess},
            {"Line": "7", "Description": "Family adjusted net income", "Amount": family_net_income},
            {"Line": "8", "Description": "Family threshold", "Amount": family_threshold},
            {"Line": "9", "Description": "Family-income excess", "Amount": family_excess},
            {"Line": "10", "Description": "Reduction base used", "Amount": reduction_base},
            {"Line": "11", "Description": "Phaseout reduction at 5%", "Amount": line11_phaseout_reduction},
            {"Line": "12 / ON428 line 85", "Description": "LIFT credit claimed", "Amount": result.get("lift_credit", 0.0)},
        ]
    )


def build_special_schedule_df(result: dict, province_code: str) -> pd.DataFrame:
    if province_code == "MB":
        rows = [
            {"Schedule": "MB428-A", "Line": "Children", "Description": "Dependent children reduction used", "Amount": result.get("provincial_tax_reduction", 0.0)},
            {"Schedule": "MB479", "Line": "Personal", "Description": "Manitoba personal tax credit", "Amount": result.get("mb479_personal_tax_credit", 0.0)},
            {"Schedule": "MB479", "Line": "Homeowners", "Description": "Homeowners affordability tax credit", "Amount": result.get("mb479_homeowners_affordability_credit", 0.0)},
            {"Schedule": "MB479", "Line": "Renters", "Description": "Renters affordability tax credit", "Amount": result.get("mb479_renters_affordability_credit", 0.0)},
            {"Schedule": "MB479", "Line": "Seniors", "Description": "Seniors school tax rebate", "Amount": result.get("mb479_seniors_school_rebate", 0.0)},
            {"Schedule": "MB479", "Line": "Caregiver", "Description": "Primary caregiver tax credit", "Amount": result.get("mb479_primary_caregiver_credit", 0.0)},
            {"Schedule": "MB479", "Line": "Fertility", "Description": "Fertility treatment tax credit", "Amount": result.get("mb479_fertility_credit", 0.0)},
        ]
        return pd.DataFrame(rows)
    if province_code == "NS":
        return pd.DataFrame(
            [
                {"Schedule": "NS479", "Line": "1", "Description": "Volunteer firefighters / ground search and rescue", "Amount": result.get("ns479_volunteer_credit", 0.0)},
                {"Schedule": "NS479", "Line": "Sports/Arts", "Description": "Children's sports and arts tax credit", "Amount": result.get("ns479_childrens_sports_arts_credit", 0.0)},
            ]
        )
    if province_code == "ON":
        return pd.DataFrame(
            [
                {"Schedule": "ON479", "Line": "Fertility", "Description": "Ontario fertility treatment tax credit", "Amount": result.get("ontario_fertility_credit", 0.0)},
                {"Schedule": "ON479", "Line": "Transit", "Description": "Ontario seniors' public transit tax credit", "Amount": result.get("ontario_seniors_transit_credit", 0.0)},
            ]
        )
    if province_code == "BC":
        return pd.DataFrame(
            [
                {"Schedule": "BC479", "Line": "Renters", "Description": "B.C. renter's tax credit", "Amount": result.get("bc_renters_credit", 0.0)},
                {"Schedule": "BC(S12)", "Line": "Home Reno", "Description": "B.C. home renovation tax credit", "Amount": result.get("bc_home_renovation_credit", 0.0)},
            ]
        )
    if province_code == "SK":
        return pd.DataFrame(
            [
                {"Schedule": "SK479", "Line": "FTTC", "Description": "Saskatchewan fertility treatment tax credit", "Amount": result.get("sk_fertility_credit", 0.0)},
            ]
        )
    if province_code == "NB":
        return pd.DataFrame(
            [
                {"Schedule": "NB428", "Line": "73", "Description": "Provincial foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
                {"Schedule": "NB428", "Line": "92+", "Description": "NB special non-refundable credits", "Amount": result.get("nb_special_non_refundable_credits", 0.0)},
                {"Schedule": "NB(S12)", "Line": "Credit", "Description": "Seniors' home renovation tax credit", "Amount": result.get("nb_seniors_home_renovation_credit", 0.0)},
            ]
        )
    if province_code == "NL":
        return pd.DataFrame(
            [
                {"Schedule": "NL428", "Line": "73", "Description": "Provincial foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
                {"Schedule": "NL428", "Line": "90+", "Description": "NL special non-refundable credits", "Amount": result.get("nl_special_non_refundable_credits", 0.0)},
                {"Schedule": "NL479", "Line": "Credit", "Description": "Other Newfoundland and Labrador refundable credits", "Amount": result.get("nl479_other_refundable_credits", 0.0)},
            ]
        )
    if province_code == "PE":
        return pd.DataFrame(
            [
                {"Schedule": "PE428", "Line": "66/99-101", "Description": "Low-income reduction used", "Amount": result.get("provincial_low_income_reduction", 0.0)},
                {"Schedule": "PE428", "Line": "89", "Description": "Provincial foreign tax credit", "Amount": result.get("provincial_foreign_tax_credit", 0.0)},
                {"Schedule": "PE428", "Line": "98", "Description": "Volunteer firefighter / search and rescue credit", "Amount": result.get("pe_volunteer_credit", 0.0)},
            ]
        )
    return pd.DataFrame()
