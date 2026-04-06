import pandas as pd


def build_client_summary_df(result: dict, province_name: str, *, format_currency) -> pd.DataFrame:
    rows = [
        {"Line": "10100", "Description": "Employment income", "Amount": result.get("line_10100", 0.0)},
        {"Line": "10400", "Description": "Other employment income", "Amount": result.get("line_10400", 0.0)},
        {"Line": "12000", "Description": "Taxable amount of dividends", "Amount": result.get("taxable_eligible_dividends", 0.0) + result.get("taxable_non_eligible_dividends", 0.0)},
        {"Line": "12100", "Description": "Interest and other investment income", "Amount": result.get("line_12100", 0.0)},
        {"Line": "12700", "Description": "Taxable capital gains", "Amount": result.get("line_taxable_capital_gains", 0.0)},
        {"Line": "15000", "Description": "Total income", "Amount": result.get("total_income", 0.0)},
        {"Line": "20700", "Description": "Registered pension plan deduction", "Amount": result.get("line_20700", 0.0)},
        {"Line": "22215", "Description": "CPP/QPP enhanced contributions on employment income", "Amount": result.get("line_22215", 0.0)},
        {"Line": "23600", "Description": "Net income", "Amount": result.get("net_income", 0.0)},
        {"Line": "26000", "Description": "Taxable income", "Amount": result.get("taxable_income", 0.0)},
        {"Line": "30000", "Description": "Basic personal amount", "Amount": result.get("line_30000", 0.0)},
        {"Line": "30300", "Description": "Spouse or common-law partner amount", "Amount": result.get("line_30300", 0.0)},
        {"Line": "30800", "Description": "CPP/QPP contributions on employment income", "Amount": result.get("line_30800", 0.0)},
        {"Line": "31200", "Description": "EI premiums on employment income", "Amount": result.get("line_31200", 0.0)},
        {"Line": "31260", "Description": "Canada employment amount", "Amount": result.get("line_31260", 0.0)},
        {"Line": "32300", "Description": "Tuition, education and textbook amount", "Amount": result.get("schedule11_total_claim_used", 0.0)},
        {"Line": "35000", "Description": "Total non-refundable tax credits", "Amount": result.get("line_35000", 0.0)},
        {"Line": "40500", "Description": "Federal foreign tax credit", "Amount": result.get("federal_foreign_tax_credit", 0.0)},
        {"Line": "42000", "Description": "Net federal tax", "Amount": result.get("line_42000", 0.0)},
        {"Line": "42800", "Description": "Provincial or territorial tax", "Amount": result.get("line_42800", 0.0)},
        {"Line": "43500", "Description": "Total payable", "Amount": result.get("line_43500", 0.0)},
        {"Line": "43700", "Description": "Total income tax deducted", "Amount": result.get("line_43700", 0.0)},
        {"Line": "45300", "Description": "Canada workers benefit", "Amount": result.get("canada_workers_benefit", 0.0)},
        {"Line": "47600", "Description": "Tax paid by instalments", "Amount": "" if result.get("line_47600", 0.0) == 0 else format_currency(result.get("line_47600", 0.0))},
        {"Line": "48200", "Description": "Total refundable credits", "Amount": result.get("line_48200", 0.0)},
        {"Line": "48400", "Description": "Refund", "Amount": result.get("line_48400_refund", 0.0)},
    ]
    df = pd.DataFrame(rows)
    df["Amount"] = df["Amount"].map(lambda value: value if isinstance(value, str) else format_currency(value))
    return df


def build_client_key_drivers_df(result: dict, province_name: str, *, build_label_amount_df) -> pd.DataFrame:
    drivers = [
        ("Total deductions", result.get("total_deductions", 0.0)),
        ("Federal non-refundable credits", result.get("federal_non_refundable_credits", 0.0)),
        (f"{province_name} non-refundable credits", result.get("provincial_non_refundable_credits", 0.0)),
        ("Refundable credits", result.get("refundable_credits", 0.0)),
        ("Income tax withheld", result.get("income_tax_withheld", 0.0)),
        ("Instalments and other payments", result.get("installments_paid", 0.0) + result.get("other_payments", 0.0)),
        ("Foreign tax credits", result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0)),
        ("Donation credits", result.get("federal_donation_credit", 0.0) + result.get("provincial_donation_credit", 0.0)),
        ("CPP/EI overpayment refunds", result.get("payroll_overpayment_refund_total", 0.0)),
    ]
    top_drivers = [(label, value) for label, value in drivers if value > 0]
    top_drivers.sort(key=lambda item: item[1], reverse=True)
    return build_label_amount_df(top_drivers[:6])


def build_client_summary_notes(
    result: dict,
    readiness_df: pd.DataFrame,
    province_name: str,
    *,
    format_currency,
) -> list[str]:
    notes: list[str] = []
    review_count = int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0
    missing_count = int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0

    if result.get("line_48400_refund", 0.0) > 0:
        notes.append(f"The current estimate shows a refund of {format_currency(result.get('line_48400_refund', 0.0))}.")
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        notes.append(f"The current estimate shows a balance owing of {format_currency(result.get('line_48500_balance_owing', 0.0))}.")
    else:
        notes.append("The current estimate is close to break-even, with little or no refund or balance owing.")

    if result.get("refundable_credits", 0.0) > 0:
        notes.append(f"Refundable credits used in this estimate total {format_currency(result.get('refundable_credits', 0.0))}.")
    if result.get("total_deductions", 0.0) > 0:
        notes.append(f"Total deductions used in the estimate are {format_currency(result.get('total_deductions', 0.0))}.")
    if result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0) > 0:
        notes.append("Foreign tax credits are included and should be matched to supporting slips or statements.")
    if result.get("schedule9_total_regular_donations_claimed", 0.0) > 0:
        notes.append("Donation claims are included and should be matched to receipts and any carryforward support.")
    if result.get("schedule11_total_claim_used", 0.0) > 0:
        notes.append("A tuition claim is included and should be matched to T2202 and any transfer/carryforward support.")
    if result.get("provincial_special_refundable_credits", 0.0) > 0:
        notes.append(f"{province_name}-specific refundable credits are included and should be reviewed against the provincial worksheet.")

    if missing_count > 0:
        notes.append(f"There are {missing_count} filing-readiness item(s) still marked Missing.")
    elif review_count > 0:
        notes.append(f"There are {review_count} filing-readiness item(s) still marked Review.")
    else:
        notes.append("No obvious filing-readiness blockers are currently showing.")

    return notes


def build_client_summary_cta(result: dict) -> str:
    if result.get("line_48500_balance_owing", 0.0) > 0:
        return "Need help reviewing the balance owing, withholding, or missing credits? Reach out at info@contexta.biz."
    if result.get("line_48400_refund", 0.0) > 0:
        return "Want help confirming the refund estimate against slips, receipts, and credits? Reach out at info@contexta.biz."
    return "If you want a second review of slips, support, filing-readiness items or others; reach out: info@contexta.biz."
