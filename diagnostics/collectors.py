from diagnostics.types import DiagnosticItem
from eligibility import (
    build_eligibility_decision,
    build_postcalc_rules_diagnostics,
    build_rules_diagnostics,
)


def collect_diagnostics(context: dict[str, float | int | bool]) -> list[DiagnosticItem]:
    checks: list[DiagnosticItem] = []

    def add(severity: str, category: str, message: str) -> None:
        checks.append((severity, category, message))

    eligibility_decision = build_eligibility_decision(
        tax_year=int(context.get("tax_year", 2025) or 2025),
        province=str(context.get("province", "") or ""),
        age=float(context.get("age", 0.0) or 0.0),
        raw_inputs=context,
        result=None,
    )

    if context["employment_income_manual"] > 0 and context["t4_income_total"] > 0:
        add("Warning", "Duplicate input", "Manual employment income and T4 Box 14 income are both entered. Confirm you are not counting the same employment income twice.")
    if context["pension_income_manual"] > 0 and (context["t4a_pension_total"] > 0 or context["t3_pension_total"] > 0):
        add("Warning", "Duplicate input", "Manual pension income and slip-based pension income are both entered. Check that line 11500/11600 income is not duplicated.")
    if context["manual_net_rental_income"] > 0 and context["t776_net_rental_income"] > 0:
        add("Warning", "Duplicate input", "Manual additional net rental income and T776 property income are both entered. Confirm the manual amount is truly separate.")
    if context["manual_taxable_capital_gains"] > 0 and context["schedule3_taxable_capital_gains"] > 0:
        add("Warning", "Duplicate input", "Manual additional taxable capital gains and Schedule 3 gains are both entered. Confirm the manual amount is not already in the Schedule 3 cards.")
    if context["manual_foreign_income"] > 0 and context["slip_foreign_income_total"] > 0:
        add("Warning", "Duplicate input", "Manual foreign income and slip-based foreign income are both entered. Confirm the manual amount is only for extra foreign income not on T5/T3/T4PS.")
    if context["manual_foreign_tax_paid"] > 0 and context["slip_foreign_tax_paid_total"] > 0:
        add("Warning", "Duplicate input", "Manual foreign tax paid and slip-based foreign tax paid are both entered. Confirm the manual amount is only for extra foreign tax not already on slips.")
    if context["tuition_amount_claim_override"] > 0 and context["t2202_tuition_total"] > 0:
        add("Info", "Tuition", "A current-year tuition override is entered while T2202 tuition is also available. This is okay if you are intentionally following Schedule 11 manually.")
    if context["spouse_claim_enabled"] and context["eligible_dependant_claim_enabled"]:
        add("High", "Household", "Spouse amount and eligible dependant are both selected. In many cases these cannot both be claimed together.")
    if context["spouse_claim_enabled"] and context["separated_in_year"]:
        add("Warning", "Household", "Spouse amount is selected while 'Separated in Year' is checked. Review whether the spouse amount should still be claimed.")
    if context["eligible_dependant_claim_enabled"] and not context["dependant_lived_with_you"]:
        add("Warning", "Household", "Eligible dependant is selected, but 'Dependant Lived With You' is not checked.")
    if context["eligible_dependant_claim_enabled"] and context["dependant_relationship"] == "Other":
        add("High", "Household", "Eligible dependant is selected, but the dependant relationship is marked as 'Other'.")
    if context["eligible_dependant_claim_enabled"] and context["dependant_category"] == "Other":
        add("High", "Household", "Eligible dependant is selected, but the dependant category is marked as 'Other'.")
    checks.extend(build_rules_diagnostics(context=context, eligibility_decision=eligibility_decision))

    if context["t4_tax_withheld_total"] > 0 and context["t4_income_total"] == 0:
        add("High", "Likely missing slip", "T4 income tax deducted is entered, but T4 Box 14 employment income is zero. Review the T4 wizard.")
    if (context["t4_cpp_total"] > 0 or context["t4_ei_total"] > 0) and context["t4_income_total"] == 0:
        add("High", "Likely missing slip", "T4 CPP/EI amounts are entered, but T4 employment income is zero. Review the T4 wizard.")
    if context["t2202_months_total"] > 0 and context["t2202_tuition_total"] == 0:
        add("Warning", "Likely missing slip", "T2202 months are entered, but eligible tuition is zero. Check T2202 Box 23/26.")
    if context["income_tax_withheld_total"] > 0 and context["estimated_total_income"] == 0:
        add("High", "Likely missing income", "Income tax deducted at source is entered, but total income is zero. You may be missing a slip or income amount.")

    if context["tuition_carryforward_claim_requested"] > context["tuition_carryforward_available_total"]:
        add("Warning", "Carryforward", "Tuition carryforward claimed exceeds the available amount. The app caps the claim, but you should review the carryforward rows.")
    if context["donation_carryforward_claim_requested"] > context["donation_carryforward_available_total"]:
        add("Warning", "Carryforward", "Donation carryforward claimed exceeds the available amount. Review the carryforward rows.")
    if context["schedule9_regular_limit_preview"] < (context["schedule9_current_year_donations_claim_requested"] + context["donation_carryforward_claim_requested"]):
        add("Info", "Schedule 9", "Total regular donations requested exceed the app's 75% of net income preview limit. The app will cap current-year and carryforward usage in the final Schedule 9 flow.")
    if context["ecological_cultural_gifts"] > 0:
        add("Info", "Schedule 9", "Ecological or cultural gifts are entered. The app treats these as outside the normal 75% of net income limit, consistent with CRA guidance.")
    if context["net_capital_loss_carryforward"] > context["taxable_capital_gains"]:
        add("Info", "Carryforward", "Requested net capital loss carryforward exceeds current taxable capital gains. The app only uses the amount that can be applied this year.")

    if context["foreign_tax_paid_total"] > 0 and context["foreign_income_total"] == 0:
        add("High", "Foreign tax", "Foreign tax paid is entered, but foreign income is zero. T2209/T2036 usually need foreign income to support the credit.")
    if context["t2209_non_business_tax_paid"] > 0 and context["t2209_net_foreign_non_business_income"] == 0:
        add("High", "Foreign tax", "T2209 tax paid is entered, but T2209 net foreign non-business income is zero.")
    if context["t2209_net_income_override"] > 0 and context["t2209_net_income_override"] < context["t2209_net_foreign_non_business_income"]:
        add("Warning", "Foreign tax", "T2209 net income override is lower than foreign non-business income. Review the worksheet override.")

    if context["income_tax_withheld_manual"] > 0 and (context["t4_tax_withheld_total"] > 0 or context["t4a_tax_withheld_total"] > 0):
        add("Info", "Withholding", "Manual other tax deducted at source and slip-based tax deducted are both entered. This can be correct, but check line 43700 is not duplicated.")
    if context["t4_box24_total"] > 0 and abs(context["t4_box24_total"] - context["estimator_ei_insurable_earnings"]) > 100.0:
        add("Info", "Withholding", "T4 Box 24 EI insurable earnings differ materially from the estimator's EI base assumption.")
    if context["t4_box26_total"] > 0 and abs(context["t4_box26_total"] - context["estimator_cpp_pensionable_earnings"]) > 100.0:
        add("Info", "Withholding", "T4 Box 26 CPP pensionable earnings differ materially from the estimator's CPP base assumption.")

    if context["canada_workers_benefit_manual"] > 0 and context["canada_workers_benefit_auto"] > 0:
        add("Info", "Refundable credits", "A manual Canada Workers Benefit override is entered. The app will use your manual amount instead of the automatic estimate.")
    if context["estimated_working_income"] <= 3000 and (context["canada_workers_benefit_manual"] > 0 or context["canada_workers_benefit_auto"] > 0):
        add("Warning", "Refundable credits", "Canada Workers Benefit is present, but working income is at or below the basic working-income threshold. Review eligibility.")
    if context["spouse_cwb_disability_supplement_eligible"] and not context["has_spouse_end_of_year"]:
        add("Warning", "Refundable credits", "Spouse CWB disability supplement eligibility is checked, but 'Had Spouse at Year End' is not checked.")
    if context["canada_training_credit_manual"] > 0 and context["canada_training_credit_limit_available"] == 0:
        add("Warning", "Refundable credits", "A Canada Training Credit override is entered, but the training credit limit available is zero.")
    if context["canada_training_credit_manual"] > context["canada_training_credit_limit_available"] and context["canada_training_credit_limit_available"] > 0:
        add("Info", "Refundable credits", "Canada Training Credit override exceeds the limit available entered. Review the training credit worksheet.")
    if context["medical_expense_supplement_manual"] > 0 and context["medical_expense_supplement_auto"] > 0:
        add("Info", "Refundable credits", "A manual Medical Expense Supplement override is entered. The app will use your manual amount instead of the automatic estimate.")
    if context["medical_expense_supplement_manual"] > 0 and context["estimated_working_income"] < 4275:
        add("Warning", "Refundable credits", "Medical Expense Supplement is entered, but employment income is below the usual earned-income threshold.")
    if (context["medical_expense_supplement_manual"] > 0 or context["medical_expense_supplement_auto"] > 0) and context["medical_claim_amount"] == 0:
        add("Warning", "Refundable credits", "Medical Expense Supplement is present, but no medical claim amount is currently available.")
    if context["cpp_overpayment_refund_auto"] > 0:
        add("Info", "Refundable credits", "CPP withheld on slips appears higher than the app's employee CPP estimate. A CPP overpayment refund estimate will be added automatically.")
    if context["ei_overpayment_refund_auto"] > 0:
        add("Info", "Refundable credits", "EI withheld on slips appears higher than the app's EI estimate. An EI overpayment refund estimate will be added automatically.")
    if context["cpp_withheld_total"] > 0 and context["estimated_working_income"] == 0:
        add("Warning", "Refundable credits", "CPP withheld is entered, but employment income is zero. Review whether a T4 employment amount is missing.")
    if context["ei_withheld_total"] > 0 and context["estimated_working_income"] == 0:
        add("Warning", "Refundable credits", "EI withheld is entered, but employment income is zero. Review whether a T4 employment amount is missing.")
    if context["manual_refundable_credits_total"] > 0 and context["provincial_special_refundable_credits"] > 0:
        add("Info", "Refundable credits", "Manual refundable credits and province-specific refundable schedule credits are both present. Confirm you are not duplicating refundable claims.")
    if context["manual_refundable_credits_total"] > 0 and context["estimated_total_income"] == 0:
        add("Warning", "Refundable credits", "Refundable credits are entered while total income is zero. Review whether the refundable claims belong in this return.")
    if context["province"] == "ON" and context["ontario_seniors_public_transit_expenses"] > 0 and context["age"] < 65:
        add("Warning", "Provincial refundable credits", "Ontario seniors' public transit expenses are entered, but age is under 65.")
    if context["province"] == "BC" and context["bc_home_renovation_expenses"] > 0 and not context["bc_home_renovation_eligible"]:
        add("Info", "Provincial refundable credits", "B.C. home renovation expenses are entered, but the eligibility checkbox is not selected.")
    if context["province"] == "BC" and context["bc_renters_credit_eligible"] and context["has_spouse_end_of_year"] and context["manual_provincial_refundable_credits"] > 0:
        add("Info", "Provincial refundable credits", "B.C. renter's credit eligibility is checked and manual provincial refundable credits are also entered. Review for duplication.")
    if context["province"] == "SK" and context["sk_fertility_treatment_expenses"] > 20000:
        add("Info", "Provincial refundable credits", "Saskatchewan fertility treatment expenses exceed $20,000. The app caps the refundable credit at the Saskatchewan maximum.")
    if context["province"] == "PE" and context["pe_volunteer_credit_eligible"] and context["manual_provincial_refundable_credits"] > 0:
        add("Info", "Provincial refundable credits", "Prince Edward Island volunteer credit eligibility is checked and manual provincial refundable credits are also entered. Review for duplication.")

    return checks


def collect_postcalc_diagnostics(result: dict[str, float]) -> list[DiagnosticItem]:
    checks: list[DiagnosticItem] = []

    def add(severity: str, category: str, message: str) -> None:
        checks.append((severity, category, message))

    checks.extend(build_postcalc_rules_diagnostics(result=result))

    refundable_total = result.get("refundable_credits", 0.0)
    total_payable = result.get("total_payable", 0.0)
    total_payments = result.get("total_payments", 0.0)
    income_tax_withheld = result.get("income_tax_withheld", 0.0)
    refund_amount = result.get("line_48400_refund", 0.0)
    if refundable_total > total_payable and total_payable > 0:
        add("Info", "Refundable credits", "Total refundable credits exceed total payable. This can be valid, but the refund result is now being driven mainly by refundable items.")
    if refund_amount > 0 and refundable_total > 0 and refundable_total >= max(1.0, total_payments * 0.5):
        add("Info", "Refundable credits", "More than half of the refund/payout is being driven by refundable credits. Review override inputs and provincial refundable schedules carefully.")
    if income_tax_withheld == 0 and refundable_total > 0 and refund_amount > 0:
        add("Info", "Refundable credits", "The return shows a refund even though no income tax was withheld, which means the result is being driven by refundable credits only.")

    if result.get("manual_provincial_refundable_credits", 0.0) > 0 and result.get("provincial_special_refundable_credits", 0.0) > 0:
        add("Info", "Refundable credits", "Manual provincial refundable credits and built-in provincial refundable schedules are both present in the final result. Check that the same provincial credit was not counted twice.")
    if result.get("ontario_seniors_public_transit_expenses", 0.0) > 0 and result.get("ontario_seniors_transit_credit", 0.0) == 0:
        add("Info", "Provincial refundable credits", "Ontario seniors' public transit expenses were entered, but no Ontario seniors' transit credit was produced. This can be correct if the age requirement is not met.")
    if result.get("bc_renters_credit_eligible", 0.0) > 0 and result.get("bc_renters_credit", 0.0) == 0:
        add("Info", "Provincial refundable credits", "B.C. renter's credit eligibility is checked, but no B.C. renter's credit was produced. Review adjusted family net income and renter eligibility.")
    if result.get("bc_home_renovation_expenses", 0.0) > 0 and result.get("bc_home_renovation_credit", 0.0) == 0:
        add("Info", "Provincial refundable credits", "B.C. home renovation expenses were entered, but no B.C. home renovation credit was produced. Review the eligibility checkbox.")
    if result.get("sk_fertility_treatment_expenses", 0.0) > 0 and result.get("sk_fertility_credit", 0.0) == 0:
        add("Info", "Provincial refundable credits", "Saskatchewan fertility treatment expenses were entered, but no Saskatchewan fertility credit was produced. Review province selection and eligible-expense entry.")
    if result.get("pe_volunteer_credit_eligible", 0.0) > 0 and result.get("pe_volunteer_credit", 0.0) == 0:
        add("Info", "Provincial refundable credits", "P.E.I. volunteer credit eligibility is checked, but no P.E.I. volunteer credit was produced. Review the PE428 volunteer-credit input.")

    if result.get("schedule9_carryforward_claim_requested", 0.0) > result.get("schedule9_carryforward_claim_used", 0.0):
        add("Info", "Schedule 9", "Donation carryforward requested exceeds the amount used in the final Schedule 9 flow. The app capped the carryforward claim to the available amount.")
    if result.get("donation_high_rate_portion", 0.0) == 0 and result.get("schedule9_total_regular_donations_claimed", 0.0) > 200 and result.get("taxable_income", 0.0) > 0:
        add("Info", "Schedule 9", "Donations above $200 were claimed, but no high-rate donation portion was produced. This can be correct if taxable income did not exceed the federal high-rate threshold.")
    if result.get("schedule9_unlimited_gifts_claimed", 0.0) > 0:
        add("Info", "Schedule 9", "Cultural or ecological gifts were included outside the regular 75% donation limit. Review line 34200 support if you are matching a CRA worksheet manually.")

    return checks
