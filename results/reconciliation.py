import pandas as pd


def _build_currency_df(rows: list[dict], currency_columns: list[str], *, format_currency) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for column in currency_columns:
        if column in df.columns:
            df[column] = df[column].map(format_currency)
    return df


def build_summary_df(result: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Item": "Total Income", "Amount": result["total_income"]},
            {"Item": "Net Income", "Amount": result["net_income"]},
            {"Item": "Taxable Income", "Amount": result["taxable_income"]},
            {"Item": "Federal Tax", "Amount": result["federal_tax"]},
            {"Item": "Provincial Tax", "Amount": result["provincial_tax"]},
            {"Item": "CPP", "Amount": result["total_cpp"]},
            {"Item": "EI", "Amount": result["ei"]},
            {"Item": "Total Payable", "Amount": result["total_payable"]},
            {"Item": "Total Payments & Credits", "Amount": result["total_payments"]},
            {"Item": "Refund / Balance Owing", "Amount": result["refund_or_balance"]},
        ]
    )


def build_return_package_df(result: dict, province_name: str, *, format_currency) -> pd.DataFrame:
    return _build_currency_df(
        [
            {"Section": "Income", "Item": "Employment income", "Amount": result.get("line_10100", 0.0)},
            {"Section": "Income", "Item": "Pension / RRSP / RRIF / other income", "Amount": result.get("line_pension_income", 0.0) + result.get("line_rrsp_rrif_income", 0.0) + result.get("line_other_income", 0.0)},
            {"Section": "Income", "Item": "Investment income and dividends", "Amount": result.get("line_interest_income", 0.0) + result.get("taxable_eligible_dividends", 0.0) + result.get("taxable_non_eligible_dividends", 0.0)},
            {"Section": "Income", "Item": "Rental and capital gains", "Amount": result.get("line_rental_income", 0.0) + result.get("line_taxable_capital_gains", 0.0)},
            {"Section": "Tax Base", "Item": "Total income", "Amount": result.get("total_income", 0.0)},
            {"Section": "Tax Base", "Item": "Net income", "Amount": result.get("net_income", 0.0)},
            {"Section": "Tax Base", "Item": "Taxable income", "Amount": result.get("taxable_income", 0.0)},
            {"Section": "Credits", "Item": "Federal non-refundable credits", "Amount": result.get("federal_non_refundable_credits", 0.0)},
            {"Section": "Credits", "Item": f"{province_name} non-refundable credits", "Amount": result.get("provincial_non_refundable_credits", 0.0)},
            {"Section": "Credits", "Item": "Refundable credits", "Amount": result.get("refundable_credits", 0.0)},
            {"Section": "Income Tax", "Item": "Federal tax", "Amount": result.get("federal_tax", 0.0)},
            {"Section": "Income Tax", "Item": f"{province_name} tax", "Amount": result.get("provincial_tax", 0.0)},
            {"Section": "Income Tax", "Item": "Total income tax payable", "Amount": result.get("total_payable", 0.0)},
            {"Section": "Payroll Contributions", "Item": "CPP and EI contributions", "Amount": result.get("total_cpp", 0.0) + result.get("ei", 0.0)},
            {"Section": "Payments", "Item": "Income tax withheld", "Amount": result.get("income_tax_withheld", 0.0)},
            {"Section": "Payments", "Item": "Instalments and other payments", "Amount": result.get("installments_paid", 0.0) + result.get("other_payments", 0.0)},
            {"Section": "Payments", "Item": "CPP/EI overpayment refunds", "Amount": result.get("payroll_overpayment_refund_total", 0.0)},
            {"Section": "Outcome", "Item": "Refund", "Amount": result.get("line_48400_refund", 0.0)},
            {"Section": "Outcome", "Item": "Balance owing", "Amount": result.get("line_48500_balance_owing", 0.0)},
        ],
        ["Amount"],
        format_currency=format_currency,
    )


def build_slip_reconciliation_df(
    result: dict,
    t4_wizard_totals: pd.Series,
    t4a_wizard_totals: pd.Series,
    t5_wizard_totals: pd.Series,
    t3_wizard_totals: pd.Series,
    t4ps_wizard_totals: pd.Series,
    t2202_wizard_totals: pd.Series,
    employment_income_manual: float,
    pension_income_manual: float,
    other_income_manual: float,
    interest_income_manual: float,
    tuition_override: float,
    *,
    format_currency,
) -> pd.DataFrame:
    def clip_non_negative(value: float) -> float:
        return max(0.0, float(value))

    def classify_row(row: dict[str, float | str]) -> dict[str, float | str]:
        difference = abs(float(row["Difference"]))
        manual_extra = float(row["Manual / Extra Input"])
        if difference < 0.01 and manual_extra == 0:
            row["Status"] = "Matched"
        elif difference < 0.01 and manual_extra > 0:
            row["Status"] = "Matched with manual input"
        else:
            row["Status"] = "Review difference"
        return row

    def build_explanation(row: dict[str, float | str]) -> str:
        area = str(row["Area"])
        slip_total = float(row["Slip Total"])
        manual_extra = float(row["Manual / Extra Input"])
        return_used = float(row["Return Amount Used"])
        difference = float(row["Difference"])
        status = str(row["Status"])
        if area == "Foreign tax credit claimed" and return_used < slip_total:
            return (
                f"You paid ${slip_total:,.2f} of foreign tax, but only "
                f"${return_used:,.2f} is claimable this year after the T2209/T2036 limits."
            )
        if area == "Interest and other investment income" and return_used == slip_total + manual_extra:
            if slip_total > 0 and manual_extra == 0:
                return (
                    "The line 12100 amount is being supported directly by slip-based interest or foreign non-business income "
                    "amounts that flow into the return."
                )
        if area == "Federal dividend tax credit" and return_used > slip_total:
            if slip_total == 0 and manual_extra > 0:
                return (
                    "No dividend tax credit was entered directly from slip credit boxes. "
                    "The return amount used includes an auto-estimated federal dividend tax credit based on the taxable dividends entered from slips."
                )
            return (
                "The final federal dividend tax credit includes the slip credit-box amounts plus an additional "
                "auto-estimated credit based on the taxable dividends entered from slips."
            )
        if status == "Matched":
            return f"{area} matched directly from slip totals with no extra allocation or override."
        if status == "Matched with manual input":
            return f"{area} matched after adding manual or non-slip inputs to the slip totals."
        if abs(difference) < 0.01 and manual_extra > 0:
            return f"{area} is fully explained by slip totals plus manual inputs."
        if return_used < slip_total + manual_extra:
            return f"{area} used less than the entered total, usually because a claim cap, allocation rule, or carryforward limit applied."
        if return_used > slip_total + manual_extra:
            return f"{area} used more than the direct slip total, which usually means extra manual inputs or another worksheet source flowed into the final return."
        return f"{area} needs review because the final amount does not reconcile cleanly to the entered slip and manual totals."

    eligible_dividend_slip_total = (
        float(t5_wizard_totals.get("box25_eligible_dividends_taxable", 0.0))
        + float(t3_wizard_totals.get("box50_eligible_dividends_taxable", 0.0))
        + float(t4ps_wizard_totals.get("box31_eligible_dividends_taxable", 0.0))
    )
    non_eligible_dividend_slip_total = (
        float(t5_wizard_totals.get("box11_non_eligible_dividends_taxable", 0.0))
        + float(t3_wizard_totals.get("box32_non_eligible_dividends_taxable", 0.0))
        + float(t4ps_wizard_totals.get("box25_non_eligible_dividends_taxable", 0.0))
    )
    foreign_income_slip_total = (
        float(t5_wizard_totals.get("box15_foreign_income", 0.0))
        + float(t3_wizard_totals.get("box25_foreign_income", 0.0))
        + float(t4ps_wizard_totals.get("box37_foreign_non_business_income", 0.0))
    )
    foreign_tax_slip_total = (
        float(t5_wizard_totals.get("box16_foreign_tax_paid", 0.0))
        + float(t3_wizard_totals.get("box34_foreign_tax_paid", 0.0))
    )
    federal_dividend_credit_slip_total = (
        float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0))
        + float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0))
        + float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0))
        + float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0))
        + float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0))
        + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0))
    )

    rows = [
        {"Group": "Income", "Area": "Employment", "Slip Total": float(t4_wizard_totals.get("box14_employment_income", 0.0)), "Manual / Extra Input": employment_income_manual, "Return Amount Used": result.get("line_10100", 0.0), "Difference": result.get("line_10100", 0.0) - (float(t4_wizard_totals.get("box14_employment_income", 0.0)) + employment_income_manual)},
        {"Group": "Income", "Area": "Pension", "Slip Total": float(t4a_wizard_totals.get("box16_pension", 0.0)) + float(t3_wizard_totals.get("box31_pension_income", 0.0)), "Manual / Extra Input": pension_income_manual, "Return Amount Used": result.get("line_pension_income", 0.0), "Difference": result.get("line_pension_income", 0.0) - (float(t4a_wizard_totals.get("box16_pension", 0.0)) + float(t3_wizard_totals.get("box31_pension_income", 0.0)) + pension_income_manual)},
        {"Group": "Income", "Area": "Other income", "Slip Total": float(t4a_wizard_totals.get("box18_lump_sum", 0.0)) + float(t4a_wizard_totals.get("box28_other_income", 0.0)) + float(t3_wizard_totals.get("box26_other_income", 0.0)) + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0)), "Manual / Extra Input": other_income_manual, "Return Amount Used": result.get("line_other_income", 0.0), "Difference": result.get("line_other_income", 0.0) - (float(t4a_wizard_totals.get("box18_lump_sum", 0.0)) + float(t4a_wizard_totals.get("box28_other_income", 0.0)) + float(t3_wizard_totals.get("box26_other_income", 0.0)) + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0)) + other_income_manual)},
        {
            "Group": "Income",
            "Area": "Interest and other investment income",
            "Slip Total": float(t5_wizard_totals.get("box13_interest", 0.0)) + foreign_income_slip_total,
            "Manual / Extra Input": interest_income_manual,
            "Return Amount Used": result.get("line_interest_income", 0.0),
            "Difference": result.get("line_interest_income", 0.0) - (float(t5_wizard_totals.get("box13_interest", 0.0)) + foreign_income_slip_total + interest_income_manual),
        },
        {"Group": "Income", "Area": "Eligible dividends", "Slip Total": eligible_dividend_slip_total, "Manual / Extra Input": clip_non_negative(result.get("taxable_eligible_dividends", 0.0) - eligible_dividend_slip_total), "Return Amount Used": result.get("taxable_eligible_dividends", 0.0), "Difference": result.get("taxable_eligible_dividends", 0.0) - (eligible_dividend_slip_total + clip_non_negative(result.get("taxable_eligible_dividends", 0.0) - eligible_dividend_slip_total))},
        {"Group": "Income", "Area": "Non-eligible dividends", "Slip Total": non_eligible_dividend_slip_total, "Manual / Extra Input": clip_non_negative(result.get("taxable_non_eligible_dividends", 0.0) - non_eligible_dividend_slip_total), "Return Amount Used": result.get("taxable_non_eligible_dividends", 0.0), "Difference": result.get("taxable_non_eligible_dividends", 0.0) - (non_eligible_dividend_slip_total + clip_non_negative(result.get("taxable_non_eligible_dividends", 0.0) - non_eligible_dividend_slip_total))},
        {"Group": "Credits", "Area": "Foreign income", "Slip Total": foreign_income_slip_total, "Manual / Extra Input": clip_non_negative(result.get("t2209_net_foreign_non_business_income", 0.0) - foreign_income_slip_total), "Return Amount Used": result.get("t2209_net_foreign_non_business_income", 0.0), "Difference": result.get("t2209_net_foreign_non_business_income", 0.0) - (foreign_income_slip_total + clip_non_negative(result.get("t2209_net_foreign_non_business_income", 0.0) - foreign_income_slip_total))},
        {"Group": "Credits", "Area": "Foreign tax paid", "Slip Total": foreign_tax_slip_total, "Manual / Extra Input": clip_non_negative(result.get("t2209_non_business_tax_paid", 0.0) - foreign_tax_slip_total), "Return Amount Used": result.get("t2209_non_business_tax_paid", 0.0), "Difference": result.get("t2209_non_business_tax_paid", 0.0) - (foreign_tax_slip_total + clip_non_negative(result.get("t2209_non_business_tax_paid", 0.0) - foreign_tax_slip_total))},
        {"Group": "Payments", "Area": "Tax withheld", "Slip Total": float(t4_wizard_totals.get("box22_tax_withheld", 0.0)) + float(t4a_wizard_totals.get("box22_tax_withheld", 0.0)), "Manual / Extra Input": max(0.0, result.get("income_tax_withheld", 0.0) - float(t4_wizard_totals.get("box22_tax_withheld", 0.0)) - float(t4a_wizard_totals.get("box22_tax_withheld", 0.0))), "Return Amount Used": result.get("income_tax_withheld", 0.0), "Difference": 0.0},
        {"Group": "Payments", "Area": "CPP withheld", "Slip Total": float(t4_wizard_totals.get("box16_cpp", 0.0)), "Manual / Extra Input": max(0.0, result.get("cpp_withheld_total", 0.0) - float(t4_wizard_totals.get("box16_cpp", 0.0))), "Return Amount Used": result.get("cpp_withheld_total", 0.0), "Difference": result.get("cpp_withheld_total", 0.0) - float(t4_wizard_totals.get("box16_cpp", 0.0)) - max(0.0, result.get("cpp_withheld_total", 0.0) - float(t4_wizard_totals.get("box16_cpp", 0.0)))},
        {"Group": "Payments", "Area": "EI withheld", "Slip Total": float(t4_wizard_totals.get("box18_ei", 0.0)), "Manual / Extra Input": max(0.0, result.get("ei_withheld_total", 0.0) - float(t4_wizard_totals.get("box18_ei", 0.0))), "Return Amount Used": result.get("ei_withheld_total", 0.0), "Difference": result.get("ei_withheld_total", 0.0) - float(t4_wizard_totals.get("box18_ei", 0.0)) - max(0.0, result.get("ei_withheld_total", 0.0) - float(t4_wizard_totals.get("box18_ei", 0.0)))},
        {"Group": "Credits", "Area": "Tuition", "Slip Total": max(float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)), float(t2202_wizard_totals.get("box23_session_tuition", 0.0))), "Manual / Extra Input": tuition_override, "Return Amount Used": result.get("schedule11_current_year_claim_used", 0.0), "Difference": result.get("schedule11_current_year_claim_used", 0.0) - (max(float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)), float(t2202_wizard_totals.get("box23_session_tuition", 0.0))) + tuition_override)},
        {"Group": "Carryforwards", "Area": "Tuition carryforward", "Slip Total": result.get("schedule11_carryforward_available", 0.0), "Manual / Extra Input": result.get("schedule11_carryforward_claim_requested", 0.0), "Return Amount Used": result.get("schedule11_carryforward_claim_used", 0.0), "Difference": result.get("schedule11_carryforward_claim_used", 0.0) - min(result.get("schedule11_carryforward_available", 0.0), result.get("schedule11_carryforward_claim_requested", 0.0))},
        {"Group": "Credits", "Area": "Current-year donations", "Slip Total": result.get("schedule9_current_year_donations_available", 0.0), "Manual / Extra Input": max(0.0, result.get("federal_dividend_tax_credit", 0.0) - federal_dividend_credit_slip_total), "Return Amount Used": result.get("schedule9_current_year_donations_claim_used", 0.0), "Difference": result.get("schedule9_current_year_donations_claim_used", 0.0) - result.get("schedule9_current_year_donations_available", 0.0)},
        {"Group": "Carryforwards", "Area": "Donation carryforward", "Slip Total": result.get("schedule9_carryforward_available", 0.0), "Manual / Extra Input": result.get("schedule9_carryforward_claim_requested", 0.0), "Return Amount Used": result.get("schedule9_carryforward_claim_used", 0.0), "Difference": result.get("schedule9_carryforward_claim_used", 0.0) - min(result.get("schedule9_carryforward_available", 0.0), result.get("schedule9_carryforward_claim_requested", 0.0))},
        {"Group": "Carryforwards", "Area": "Capital loss carryforward", "Slip Total": result.get("net_capital_loss_carryforward_requested", 0.0), "Manual / Extra Input": result.get("line_taxable_capital_gains", 0.0), "Return Amount Used": result.get("net_capital_loss_carryforward", 0.0), "Difference": result.get("net_capital_loss_carryforward", 0.0) - min(result.get("net_capital_loss_carryforward_requested", 0.0), result.get("line_taxable_capital_gains", 0.0))},
        {"Group": "Credits", "Area": "Refundable credits", "Slip Total": result.get("federal_refundable_credits", 0.0) + result.get("provincial_special_refundable_credits", 0.0), "Manual / Extra Input": result.get("manual_provincial_refundable_credits", 0.0) + result.get("other_manual_refundable_credits", 0.0), "Return Amount Used": result.get("refundable_credits", 0.0), "Difference": result.get("refundable_credits", 0.0) - (result.get("federal_refundable_credits", 0.0) + result.get("provincial_special_refundable_credits", 0.0) + result.get("manual_provincial_refundable_credits", 0.0) + result.get("other_manual_refundable_credits", 0.0))},
        {"Group": "Credits", "Area": "Federal dividend tax credit", "Slip Total": federal_dividend_credit_slip_total, "Manual / Extra Input": 0.0, "Return Amount Used": result.get("federal_dividend_tax_credit", 0.0), "Difference": result.get("federal_dividend_tax_credit", 0.0) - federal_dividend_credit_slip_total},
        {"Group": "Credits", "Area": "Foreign tax credit claimed", "Slip Total": result.get("t2209_non_business_tax_paid", 0.0), "Manual / Extra Input": 0.0, "Return Amount Used": result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0), "Difference": (result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0)) - result.get("t2209_non_business_tax_paid", 0.0)},
        {"Group": "Credits", "Area": "Household claims", "Slip Total": result.get("manual_spouse_claim", 0.0) + result.get("manual_eligible_dependant_claim", 0.0), "Manual / Extra Input": result.get("auto_spouse_amount", 0.0) + result.get("auto_eligible_dependant_amount", 0.0), "Return Amount Used": result.get("effective_spouse_claim", 0.0) + result.get("effective_eligible_dependant_claim", 0.0) + result.get("provincial_caregiver_claim_amount", 0.0) + result.get("household_disability_transfer_used", 0.0), "Difference": (result.get("effective_spouse_claim", 0.0) + result.get("effective_eligible_dependant_claim", 0.0) + result.get("provincial_caregiver_claim_amount", 0.0) + result.get("household_disability_transfer_used", 0.0)) - (result.get("manual_spouse_claim", 0.0) + result.get("manual_eligible_dependant_claim", 0.0) + result.get("auto_spouse_amount", 0.0) + result.get("auto_eligible_dependant_amount", 0.0))},
    ]

    for row in rows:
        classify_row(row)
        row["Explanation"] = build_explanation(row)

    return _build_currency_df(rows, ["Slip Total", "Manual / Extra Input", "Return Amount Used", "Difference"], format_currency=format_currency)


def build_assumptions_overrides_df(
    result: dict,
    province_name: str,
    tuition_claim_override: float,
    t2209_net_income_override: float,
    t2209_basic_federal_tax_override: float,
    t2036_provincial_tax_otherwise_payable_override: float,
    *,
    format_currency,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(area: str, item: str, treatment: str, detail: str) -> None:
        rows.append({"Area": area, "Item": item, "Treatment": treatment, "Detail": detail})

    if tuition_claim_override > 0:
        add("Schedule 11", "Current-year tuition claim", "Manual override used", f"You entered a direct current-year tuition claim override of {format_currency(tuition_claim_override)}.")
    elif result.get("schedule11_current_year_tuition_available", 0.0) > 0:
        add("Schedule 11", "Current-year tuition claim", "Auto / slip-based flow", f"The app used the T2202-driven Schedule 11 flow and claimed {format_currency(result.get('schedule11_current_year_claim_used', 0.0))}.")

    if t2209_net_income_override > 0:
        add("T2209", "Net income used for foreign tax credit limit", "Manual override used", f"The T2209 limit used a manual net-income override of {format_currency(t2209_net_income_override)} instead of the return net income.")
    elif result.get("federal_foreign_tax_credit", 0.0) > 0:
        add("T2209", "Net income used for foreign tax credit limit", "Return value used", f"The app used return net income of {format_currency(result.get('t2209_net_income', 0.0))} in the T2209 limit flow.")

    if t2209_basic_federal_tax_override > 0:
        add("T2209", "Basic federal tax used", "Manual override used", f"The T2209 federal limit used a manual basic-federal-tax override of {format_currency(t2209_basic_federal_tax_override)}.")
    elif result.get("federal_foreign_tax_credit", 0.0) > 0:
        add("T2209", "Basic federal tax used", "Calculated value used", f"The app used calculated federal tax of {format_currency(result.get('t2209_basic_federal_tax_used', 0.0))} in the foreign tax credit ceiling.")

    if t2036_provincial_tax_otherwise_payable_override > 0:
        add("T2036", f"{province_name} tax otherwise payable", "Manual override used", f"The provincial foreign tax credit used a manual override of {format_currency(t2036_provincial_tax_otherwise_payable_override)}.")
    elif result.get("provincial_foreign_tax_credit", 0.0) > 0:
        add("T2036", f"{province_name} tax otherwise payable", "Calculated value used", f"The app used {format_currency(result.get('provincial_tax_otherwise_payable', 0.0))} as provincial tax otherwise payable.")

    cwb_manual = result.get("canada_workers_benefit_manual", 0.0)
    cwb_auto = result.get("canada_workers_benefit_auto", 0.0)
    if cwb_manual > 0:
        add("Refundable credits", "Canada Workers Benefit", "Manual override used", f"The final CWB used the manual amount of {format_currency(cwb_manual)}. Auto estimate was {format_currency(cwb_auto)}.")
    elif cwb_auto > 0:
        add("Refundable credits", "Canada Workers Benefit", "Auto estimate used", f"The app auto-estimated CWB at {format_currency(result.get('canada_workers_benefit', 0.0))}.")

    training_manual = result.get("canada_training_credit_manual", 0.0)
    training_auto = result.get("canada_training_credit_auto", 0.0)
    if training_manual > 0:
        add("Refundable credits", "Canada Training Credit", "Manual override used", f"The final training credit used the manual amount of {format_currency(training_manual)}. Auto estimate was {format_currency(training_auto)}.")
    elif training_auto > 0:
        add("Refundable credits", "Canada Training Credit", "Auto estimate used", f"The app auto-estimated the Canada Training Credit at {format_currency(result.get('canada_training_credit', 0.0))}.")

    medical_manual = result.get("medical_expense_supplement_manual", 0.0)
    medical_auto = result.get("medical_expense_supplement_auto", 0.0)
    if medical_manual > 0:
        add("Refundable credits", "Medical Expense Supplement", "Manual override used", f"The final medical supplement used the manual amount of {format_currency(medical_manual)}. Auto estimate was {format_currency(medical_auto)}.")
    elif medical_auto > 0:
        add("Refundable credits", "Medical Expense Supplement", "Auto estimate used", f"The app auto-estimated the medical expense supplement at {format_currency(result.get('medical_expense_supplement', 0.0))}.")

    if result.get("schedule11_carryforward_claim_requested", 0.0) > result.get("schedule11_carryforward_claim_used", 0.0):
        add("Schedule 11", "Tuition carryforward claim", "Capped by available amount", f"Requested {format_currency(result.get('schedule11_carryforward_claim_requested', 0.0))}, but only {format_currency(result.get('schedule11_carryforward_claim_used', 0.0))} was used.")
    if result.get("net_capital_loss_carryforward_requested", 0.0) > result.get("net_capital_loss_carryforward", 0.0):
        add("Schedule 3", "Net capital loss carryforward", "Capped by current-year gain", f"Requested {format_currency(result.get('net_capital_loss_carryforward_requested', 0.0))}, but only {format_currency(result.get('net_capital_loss_carryforward', 0.0))} could be used.")
    if result.get("schedule9_carryforward_claim_requested", 0.0) > result.get("schedule9_carryforward_claim_used", 0.0):
        add("Schedule 9", "Donation carryforward", "Capped by available amount / regular limit", f"Requested {format_currency(result.get('schedule9_carryforward_claim_requested', 0.0))}, but only {format_currency(result.get('schedule9_carryforward_claim_used', 0.0))} was used.")

    if not rows:
        add("General", "Assumptions and overrides", "Default calculation path", "No major manual override or cap-driven adjustment was detected in the final return.")

    return pd.DataFrame(rows)


def build_missing_support_df(result: dict, province: str, province_name: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(area: str, support_needed: str, reason: str, priority: str = "Core") -> None:
        rows.append(
            {
                "Priority": priority,
                "Area": area,
                "Suggested Support": support_needed,
                "Why It Matters": reason,
            }
        )

    if result.get("line_10100", 0.0) > 0 or result.get("income_tax_withheld", 0.0) > 0:
        add("Employment", "T4 slips and payroll summaries", "Employment income, withholding, CPP, or EI is part of the return.")
    if result.get("line_pension_income", 0.0) > 0 or result.get("line_other_income", 0.0) > 0:
        add("Pension / other income", "T4A, T3, T4PS, or supporting slips", "Pension or other income is being reported from slip or manual sources.")
    if result.get("line_interest_income", 0.0) > 0 or result.get("taxable_eligible_dividends", 0.0) > 0 or result.get("taxable_non_eligible_dividends", 0.0) > 0:
        add("Investment income", "T5 / T3 / T4PS slips and dividend summaries", "Interest or dividend income is included in the return.")
    if result.get("line_taxable_capital_gains", 0.0) > 0 or result.get("net_capital_loss_carryforward", 0.0) > 0:
        add("Schedule 3", "Sale documents, ACB records, and outlay support", "Capital gains or capital-loss carryforward usage affects line 12700.")
    if result.get("line_rental_income", 0.0) != 0:
        add("T776", "Rental income and expense records", "Net rental income is being reported from the rental-property workflow.")
    if result.get("schedule11_total_claim_used", 0.0) > 0 or result.get("schedule11_transfer_from_spouse", 0.0) > 0:
        add("Schedule 11", "T2202 and tuition transfer support", "Tuition claim or transfer is part of the final return.")
    if result.get("federal_foreign_tax_credit", 0.0) > 0 or result.get("provincial_foreign_tax_credit", 0.0) > 0:
        add("Foreign tax credit", "Foreign-income slips, tax statements, and T2209/T2036 support", "Foreign tax credit is being claimed federally and/or provincially.")
    if result.get("schedule9_total_regular_donations_claimed", 0.0) > 0 or result.get("schedule9_unlimited_gifts_claimed", 0.0) > 0:
        add("Schedule 9", "Donation receipts and gift support", "Donation credits or gifts outside the regular limit are part of the return.")
    if result.get("federal_medical_claim", 0.0) > 0 or result.get("medical_expense_supplement", 0.0) > 0:
        add("Medical", "Medical receipts and dependant-medical support", "Medical expenses affect non-refundable and/or refundable credits.")
    if result.get("effective_spouse_claim", 0.0) > 0 or result.get("effective_eligible_dependant_claim", 0.0) > 0 or result.get("provincial_caregiver_claim_amount", 0.0) > 0:
        add("Household claims", "Proof of marital/dependant status and support restrictions", "Household claim eligibility changes federal and provincial credits.")
    if result.get("household_disability_transfer_used", 0.0) > 0:
        add("Disability transfer", "Disability certificate / unused transfer support", "A disability transfer is being used in the return.")
    if result.get("provincial_special_refundable_credits", 0.0) > 0:
        support_by_province = {
            "ON": "ON479 support for fertility treatment / seniors' transit credit",
            "BC": "BC479 / BC(S12) support for renter or home-renovation credit",
            "MB": "MB479 support for refundable credit claims",
            "NS": "NS479 support for volunteer or children's credit",
            "NB": "NB(S12) support for seniors' home renovation credit",
            "NL": "NL479 support for refundable credit claims",
            "SK": "SK479 support for fertility treatment credit",
            "PE": "PE volunteer / low-income support",
        }
        add("Provincial refundable credits", support_by_province.get(province, f"{province_name} refundable-credit support"), "A built-in provincial refundable or benefit-style credit is part of the return.")
    if not rows:
        add("General", "No obvious extra support flagged", "The current return does not show special schedules that usually need extra support beyond core slips.", "Info")

    return pd.DataFrame(rows)
