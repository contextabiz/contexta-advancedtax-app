import pandas as pd

from .types import DiagnosticItem


def build_filing_readiness_df(
    result: dict,
    diagnostics: list[DiagnosticItem],
    postcalc_diagnostics: list[DiagnosticItem],
    province: str,
    province_name: str,
) -> pd.DataFrame:
    combined_messages = " ".join(message.lower() for _, _, message in diagnostics + postcalc_diagnostics)
    rows: list[dict[str, str]] = []

    def add(status: str, area: str, checklist_item: str, detail: str) -> None:
        rows.append(
            {
                "Status": status,
                "Area": area,
                "Checklist Item": checklist_item,
                "Detail": detail,
            }
        )

    if result.get("line_10100", 0.0) > 0:
        add(
            "Ready" if result.get("income_tax_withheld", 0.0) > 0 else "Review",
            "Employment",
            "Employment slips entered",
            "Employment income is present. Confirm T4 slip amounts and withholding have been matched before filing.",
        )

    if result.get("line_pension_income", 0.0) > 0 or result.get("line_other_income", 0.0) > 0:
        status = "Review" if "duplicate" in combined_messages else "Ready"
        add(
            status,
            "Pension / Other income",
            "Other-slip income reviewed",
            "Pension or other income is included. Check T4A/T3/T4PS support and confirm no overlap with manual inputs.",
        )

    if result.get("line_rental_income", 0.0) != 0:
        add(
            "Review",
            "T776",
            "Rental support assembled",
            "Rental activity is part of the return. Review gross rents, expenses, and CCA support before treating the estimate as filing-ready.",
        )

    if result.get("line_taxable_capital_gains", 0.0) > 0 or result.get("net_capital_loss_carryforward", 0.0) > 0:
        add(
            "Review",
            "Schedule 3",
            "Capital property records reviewed",
            "Capital gains and/or net capital loss carryforwards affect line 12700. Confirm proceeds, ACB, outlays, and carryforward support.",
        )

    if result.get("schedule11_total_claim_used", 0.0) > 0:
        add(
            "Ready" if result.get("schedule11_current_year_tuition_available", 0.0) > 0 else "Review",
            "Schedule 11",
            "Tuition support available",
            "Tuition was claimed. Confirm T2202 support and any transfer / carryforward amounts used.",
        )

    if result.get("federal_foreign_tax_credit", 0.0) > 0 or result.get("provincial_foreign_tax_credit", 0.0) > 0:
        foreign_status = (
            "Review"
            if result.get("t2209_net_income_override", 0.0) > 0
            or result.get("t2209_basic_federal_tax_override", 0.0) > 0
            or result.get("t2036_provincial_tax_otherwise_payable_override", 0.0) > 0
            else "Ready"
        )
        add(
            foreign_status,
            "T2209 / T2036",
            "Foreign tax credit support reviewed",
            "Foreign tax credits are being claimed. Confirm foreign-income support and whether any worksheet overrides were intentional.",
        )

    if result.get("schedule9_total_regular_donations_claimed", 0.0) > 0 or result.get("schedule9_unlimited_gifts_claimed", 0.0) > 0:
        add(
            "Review" if result.get("schedule9_carryforward_claim_requested", 0.0) > result.get("schedule9_carryforward_claim_used", 0.0) else "Ready",
            "Schedule 9",
            "Donation support reviewed",
            "Donations or gifts are claimed. Confirm current-year receipts, carryforward support, and any ecological/cultural gift documentation.",
        )

    if result.get("effective_spouse_claim", 0.0) > 0 or result.get("effective_eligible_dependant_claim", 0.0) > 0 or result.get("provincial_caregiver_claim_amount", 0.0) > 0:
        household_status = "Review" if "household" in combined_messages else "Ready"
        add(
            household_status,
            "Household claims",
            "Household eligibility confirmed",
            "Spouse, dependant, caregiver, or related household claims are in play. Confirm marital status, support arrangements, and dependant eligibility.",
        )

    if result.get("refundable_credits", 0.0) > 0:
        refundable_status = "Review" if "manual" in combined_messages or "override" in combined_messages else "Ready"
        add(
            refundable_status,
            "Refundable credits",
            "Refundable-credit support reviewed",
            "Refundable credits affect the outcome. Review any auto-estimated or manually overridden refundable items before treating the result as filing-ready.",
        )

    if result.get("provincial_special_refundable_credits", 0.0) > 0:
        add(
            "Review",
            f"{province_name} special schedules",
            "Province-specific refundable schedule checked",
            f"{province_name} special refundable credits are included. Confirm the relevant provincial schedule support before filing.",
        )

    if result.get("line_48400_refund", 0.0) > 0:
        add(
            "Ready" if result.get("income_tax_withheld", 0.0) > 0 or result.get("refundable_credits", 0.0) > 0 else "Missing",
            "Outcome",
            "Refund explanation is supportable",
            "A refund is showing. Confirm it is explained by withholding, refundable credits, or payroll overpayment refunds.",
        )
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        add(
            "Ready",
            "Outcome",
            "Balance owing is explained",
            "A balance owing is showing. Confirm instalments, withholding, and deductions were entered completely.",
        )

    if any(severity == "High" for severity, _, _ in diagnostics):
        add(
            "Missing",
            "Diagnostics",
            "High-risk pre-calculation issues resolved",
            "At least one high-risk diagnostic is still present. Review the Pre-Calculation Diagnostics before relying on the return.",
        )
    if any(severity == "Warning" for severity, _, _ in postcalc_diagnostics):
        add(
            "Review",
            "Diagnostics",
            "Post-calculation warnings reviewed",
            "At least one post-calculation warning is still present. Review refundable-credit and payment-allocation warnings.",
        )

    if not rows:
        add(
            "Review",
            "General",
            "Return readiness not yet established",
            "The app does not yet have enough active return content to assess filing readiness in a meaningful way.",
        )

    return pd.DataFrame(rows)


def build_results_quick_notes(
    result: dict,
    readiness_df: pd.DataFrame,
    diagnostics: list[DiagnosticItem],
    postcalc_diagnostics: list[DiagnosticItem],
    reconciliation_df: pd.DataFrame | None = None,
    assumptions_df: pd.DataFrame | None = None,
    *,
    format_currency,
) -> tuple[list[str], list[str], list[str]]:
    quick_review_items: list[str] = []
    top_warning_items: list[str] = []
    top_override_items: list[str] = []

    if result.get("line_48400_refund", 0.0) > 0:
        quick_review_items.append(
            f"Estimated refund: {format_currency(result.get('line_48400_refund', 0.0))}."
        )
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        quick_review_items.append(
            f"Estimated balance owing: {format_currency(result.get('line_48500_balance_owing', 0.0))}."
        )
    else:
        quick_review_items.append("The estimate is currently close to break-even.")

    ready_count = int((readiness_df["Status"] == "Ready").sum()) if not readiness_df.empty else 0
    review_count = int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0
    missing_count = int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0
    quick_review_items.append(
        f"Filing-readiness snapshot: Ready {ready_count}, Review {review_count}, Missing {missing_count}."
    )

    if not readiness_df.empty:
        flagged_rows = readiness_df[readiness_df["Status"].astype(str) != "Ready"].head(3)
        for _, row in flagged_rows.iterrows():
            item = f'{row["Status"]}: {row["Checklist Item"]}'
            quick_review_items.append(item)
            if len(top_warning_items) < 3:
                top_warning_items.append(item)

    for severity, category, message in (diagnostics or [])[:2]:
        top_warning_items.append(f"{severity} - {category}: {message}")
    for severity, category, message in (postcalc_diagnostics or [])[:2]:
        top_warning_items.append(f"{severity} - {category}: {message}")

    if assumptions_df is not None and not assumptions_df.empty:
        flagged_overrides = assumptions_df[
            assumptions_df["Treatment"].astype(str).str.contains("Manual Override|Cap Applied", case=False, regex=True)
        ]
        for _, row in flagged_overrides.head(3).iterrows():
            top_override_items.append(f'{row["Item"]} ({row["Treatment"]})')

    if reconciliation_df is not None and not reconciliation_df.empty:
        flagged_reconciliation = reconciliation_df[reconciliation_df["Status"].astype(str) == "Review difference"]
        for _, row in flagged_reconciliation.head(2).iterrows():
            top_warning_items.append(f'{row["Area"]}: review the difference shown in input checks.')

    return quick_review_items[:6], top_warning_items[:4], top_override_items[:3]
