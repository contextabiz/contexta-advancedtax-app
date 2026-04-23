import streamlit as st

from results.summary_panels import build_tax_optimization_items
from ui_config import (
    PLANNING_PRIORITY_THRESHOLDS,
    STEP5_CHECKPOINT_SHORT_BODIES,
    STEP5_SECTION_COPY,
    STEP5_STATUS_BADGE_STYLES,
)


def build_step5_optimization_preview(
    *,
    session_state,
    t2202_wizard_totals,
    t4_wizard_totals,
    deduction_preview_total: float,
    balance_owing_preview: float,
) -> dict:
    tuition_available = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)) or float(
        t2202_wizard_totals.get("box23_session_tuition", 0.0)
    )
    tuition_claim_requested = float(session_state.get("tuition_amount_claim", 0.0))
    charitable_donations = float(session_state.get("charitable_donations", 0.0))
    donation_detail_total = float(session_state.get("donations_eligible_total", 0.0))
    income_tax_withheld_preview = (
        float(session_state.get("income_tax_withheld", 0.0))
        + float(t4_wizard_totals.get("box22_tax_withheld", 0.0))
    )
    cwb_manual_amount = float(session_state.get("canada_workers_benefit", 0.0))

    return {
        "line_30300": 0.0,
        "spouse_net_income_for_lift": float(session_state.get("spouse_net_income", session_state.get("persist_spouse_net_income", 0.0))),
        "schedule11_total_available": tuition_available,
        "schedule11_total_claim_used": tuition_claim_requested,
        "line_48500_balance_owing": max(0.0, balance_owing_preview),
        "line_48400_refund": 0.0,
        "total_deductions": deduction_preview_total,
        "canada_workers_benefit": cwb_manual_amount,
        "schedule9_total_regular_donations_claimed": max(charitable_donations, donation_detail_total),
        "federal_donation_credit": 0.0,
        "federal_foreign_tax_credit": 0.0,
        "provincial_foreign_tax_credit": 0.0,
        "income_tax_withheld": income_tax_withheld_preview,
    }


def build_step5_checkpoint_suggestions(
    *,
    session_state,
    t2202_wizard_totals,
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []

    def add_item(item_id: str, label: str, reason: str, where: str) -> None:
        suggestions.append(
            {
                "id": item_id,
                "label": label,
                "reason": reason,
                "where": where,
            }
        )

    spouse_net_income = float(session_state.get("spouse_net_income", session_state.get("persist_spouse_net_income", 0.0)))
    tuition_available = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)) or float(
        t2202_wizard_totals.get("box23_session_tuition", 0.0)
    )
    medical_expenses_paid = float(session_state.get("medical_expenses_paid", 0.0))
    charitable_donations = float(session_state.get("charitable_donations", 0.0))
    canada_workers_benefit = float(session_state.get("canada_workers_benefit", 0.0))
    foreign_income = float(session_state.get("foreign_income", 0.0))
    foreign_tax_paid = float(session_state.get("foreign_tax_paid", 0.0))

    if spouse_net_income > 0.0 and spouse_net_income < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]:
        add_item(
            "spouse_amount",
            "Check the spouse / common-law partner amount.",
            "This can reduce tax if your spouse or partner had low net income.",
            "Step 5 -> Family and Household Questions",
        )
    if tuition_available > 0.0 or float(session_state.get("student_loan_interest", 0.0)) > 0.0:
        add_item(
            "tuition_and_student",
            "Check tuition, student loan interest, and any tuition carryforward amounts.",
            "These amounts often create credits now or preserve carryforwards for later years.",
            "Step 5 -> Common Credits You Might Claim or Step 5 -> Prior-Year Carryforwards and Transfers",
        )
    if medical_expenses_paid > 0.0 or charitable_donations > 0.0:
        add_item(
            "medical_and_donations",
            "Check medical expenses and charitable donations.",
            "Even moderate amounts can create useful non-refundable credits.",
            "Step 5 -> Common Credits You Might Claim",
        )
    if canada_workers_benefit > 0.0 or bool(session_state.get("cwb_basic_eligible", False)):
        add_item(
            "low_income_refundable",
            "Check whether Canada Workers Benefit or Medical Expense Supplement may apply.",
            "Lower-income returns often qualify for refundable support that changes the final result.",
            "Step 5 -> Refundable Credits and Income-Tested Support",
        )
    if foreign_income > 0.0 or foreign_tax_paid > 0.0:
        add_item(
            "foreign_and_investment",
            "Review foreign income and foreign tax inputs.",
            "Foreign income and foreign tax amounts are easy to misclassify or count twice.",
            "Step 5 -> Foreign Income, Dividend Credits, and Manual Overrides",
        )

    return suggestions


def render_step5_optimization_checkpoint(
    result_preview: dict,
    suggestions: list[dict] | None = None,
    *,
    format_currency,
) -> None:
    items = build_tax_optimization_items(result_preview, suggestions, format_currency=format_currency)
    if not items:
        return

    with st.container(border=True):
        st.markdown("##### Optimization Checkpoint")
        st.caption("Before you continue, here is what looks most worth your time in this step based on what is already entered.")
        for title, body in items[:3]:
            st.markdown(f"- **{title}**: {STEP5_CHECKPOINT_SHORT_BODIES.get(title, body)}")


def build_step5_section_statuses(
    *,
    session_state,
    t2202_wizard_totals,
    province_name: str,
) -> dict[str, dict[str, str]]:
    spouse_net_income = float(session_state.get("spouse_net_income", session_state.get("persist_spouse_net_income", 0.0)))
    has_spouse_end_of_year = bool(session_state.get("has_spouse_end_of_year", session_state.get("persist_has_spouse_end_of_year", False)))
    spouse_claim_enabled = bool(session_state.get("spouse_claim_enabled", session_state.get("persist_spouse_claim_enabled", False)))
    eligible_dependant_claim_enabled = bool(
        session_state.get("eligible_dependant_claim_enabled", session_state.get("persist_eligible_dependant_claim_enabled", False))
    )
    tuition_available = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)) or float(
        t2202_wizard_totals.get("box23_session_tuition", 0.0)
    )
    tuition_claim_requested = float(session_state.get("tuition_amount_claim", 0.0))
    tuition_transfer_from_spouse = float(session_state.get("tuition_transfer_from_spouse", 0.0))
    student_loan_interest = float(session_state.get("student_loan_interest", 0.0))
    medical_expenses_paid = float(session_state.get("medical_expenses_paid", 0.0))
    charitable_donations = float(session_state.get("charitable_donations", 0.0))
    disability_amount_claim = float(session_state.get("disability_amount_claim", 0.0))
    additional_federal_credits = float(session_state.get("additional_federal_credits", 0.0))
    additional_provincial_credit_amount = float(session_state.get("additional_provincial_credit_amount", 0.0))
    cwb_basic_eligible = bool(session_state.get("cwb_basic_eligible", session_state.get("persist_cwb_basic_eligible", False)))
    cwb_disability_supplement_eligible = bool(
        session_state.get("cwb_disability_supplement_eligible", session_state.get("persist_cwb_disability_supplement_eligible", False))
    )
    canada_workers_benefit = float(session_state.get("canada_workers_benefit", 0.0))
    canada_training_credit_limit_available = float(session_state.get("canada_training_credit_limit_available", 0.0))
    canada_training_credit = float(session_state.get("canada_training_credit", 0.0))
    medical_expense_supplement = float(session_state.get("medical_expense_supplement", 0.0))
    foreign_income = float(session_state.get("foreign_income", 0.0))
    foreign_tax_paid = float(session_state.get("foreign_tax_paid", 0.0))
    provincial_dividend_tax_credit_manual = float(session_state.get("provincial_dividend_tax_credit_manual", 0.0))
    tuition_carryforward_records = st.session_state.get("persist_tuition_carryforwards", st.session_state.get("tuition_carryforwards", [])) or []
    donation_carryforward_records = st.session_state.get("persist_donation_carryforwards", st.session_state.get("donation_carryforwards", [])) or []

    statuses = {
        key: value.copy()
        for key, value in STEP5_SECTION_COPY.items()
    }
    statuses["province_special"] = {
        "status": "Review if applicable",
        "why": f"Open this only if a {province_name} worksheet, special schedule, or province-specific credit clearly applies.",
        "note": "This is usually only relevant for special provincial cases.",
    }

    if any(value > 0.0 for value in [tuition_available, student_loan_interest, medical_expenses_paid, charitable_donations]):
        statuses["common_credits"] = {
            "status": "Looks underused" if tuition_available > 0.0 and tuition_claim_requested <= 0.0 else "Already active",
            "why": "This section controls the most common Step 5 credits that often change the final result quickly.",
            "note": (
                "Tuition is showing but no manual claim has been requested yet."
                if tuition_available > 0.0 and tuition_claim_requested <= 0.0
                else "A common-credit input is already active here."
            ),
        }

    if spouse_claim_enabled or has_spouse_end_of_year or eligible_dependant_claim_enabled:
        statuses["household"] = {
            "status": "Looks underused" if has_spouse_end_of_year and spouse_net_income > 0.0 else "Already active",
            "why": "Household facts decide whether spouse amount, eligible dependant, caregiver, and disability-transfer claims are available or blocked.",
            "note": (
                "Spouse or dependant facts are already showing and may still support a claim review."
                if has_spouse_end_of_year or eligible_dependant_claim_enabled
                else "Household review is already active."
            ),
        }

    if any(value > 0.0 for value in [disability_amount_claim, tuition_claim_requested, tuition_transfer_from_spouse, additional_federal_credits, additional_provincial_credit_amount]):
        statuses["manual_overrides"] = {
            "status": "Already active",
            "why": "A manual amount is already in play here, so this section now affects the estimate directly.",
            "note": "Keep this open only for fields you intend to override manually.",
        }

    if cwb_basic_eligible or cwb_disability_supplement_eligible or any(
        value > 0.0 for value in [canada_workers_benefit, canada_training_credit_limit_available, canada_training_credit, medical_expense_supplement]
    ):
        statuses["refundable"] = {
            "status": "Already active" if any(value > 0.0 for value in [canada_workers_benefit, canada_training_credit, medical_expense_supplement]) else "Looks underused",
            "why": "Refundable and income-tested support can move the file even when non-refundable credits are already fully used.",
            "note": (
                "An eligibility signal is on, but the section may still need amounts or confirmation."
                if cwb_basic_eligible and canada_workers_benefit <= 0.0
                else "A refundable-credit input is already active here."
            ),
        }

    if foreign_income > 0.0 or foreign_tax_paid > 0.0 or provincial_dividend_tax_credit_manual > 0.0:
        statuses["foreign"] = {
            "status": "Already active",
            "why": "Foreign income and foreign tax details are easy to misclassify, so this section matters whenever those amounts are in play.",
            "note": "Manual foreign-income, foreign-tax, or dividend-credit inputs are already active.",
        }

    if tuition_carryforward_records or donation_carryforward_records or tuition_transfer_from_spouse > 0.0:
        statuses["carryforwards"] = {
            "status": "Already active",
            "why": "Carryforwards and transfers affect what can still be claimed now versus preserved for later years.",
            "note": "A carryforward or transfer input is already recorded here.",
        }
    elif tuition_available > 0.0:
        statuses["carryforwards"] = {
            "status": "Review if applicable",
            "why": "If current-year tuition is not fully used, this section helps position what gets claimed now versus carried forward.",
            "note": "Current-year tuition is showing, so carryforward treatment may still matter.",
        }

    return statuses


def render_step5_section_intro(section: dict[str, str]) -> None:
    style = STEP5_STATUS_BADGE_STYLES.get(section["status"], STEP5_STATUS_BADGE_STYLES["Review if applicable"])
    status_html = ""
    if section["status"] != "Probably skip":
        status_html = (
            f"<span style='display:inline-block;padding:4px 10px;border-radius:999px;background:{style['bg']};"
            f"color:{style['fg']};border:1px solid {style['border']};font-size:0.74rem;font-weight:700;"
            f"letter-spacing:0.04em;text-transform:uppercase;'>{section['status']}</span>"
        )
    st.markdown(
        (
            "<div style='border:1px solid rgba(255,255,255,0.08);border-radius:14px;"
            "padding:12px 14px;margin:8px 0 14px 0;background:#101826;'>"
            "<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;'>"
            f"{status_html}"
            "</div>"
            f"<div style='color:#D9E3F0;font-size:0.93rem;line-height:1.55;margin-bottom:6px;'><strong>Why this matters:</strong> {section['why']}</div>"
            f"<div style='color:#9FB2C9;font-size:0.90rem;line-height:1.5;'>{section['note']}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_step5_why_card(why: str, note: str = "") -> None:
    note_html = ""
    if note:
        note_html = f"<div style='color:#9FB2C9;font-size:0.90rem;line-height:1.5;'>{note}</div>"
    st.markdown(
        (
            "<div style='border:1px solid rgba(255,255,255,0.08);border-radius:14px;"
            "padding:12px 14px;margin:8px 0 14px 0;background:#101826;'>"
            f"<div style='color:#D9E3F0;font-size:0.93rem;line-height:1.55;margin-bottom:6px;'><strong>Why this matters:</strong> {why}</div>"
            f"{note_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def summarize_carryforward_records(records: list[dict[str, object]]) -> tuple[float, float, float]:
    total_available = 0.0
    total_requested = 0.0
    total_used = 0.0
    for row in records:
        available = float(row.get("available_amount", 0.0) or 0.0)
        requested = float(row.get("claim_amount", 0.0) or 0.0)
        used = min(available, requested)
        total_available += available
        total_requested += requested
        total_used += used
    return total_available, total_requested, total_used


def render_carryforward_mini_worksheet(title: str, records: list[dict[str, object]], *, build_currency_df, render_metric_row) -> None:
    available, requested, used = summarize_carryforward_records(records)
    unused = max(0.0, available - used)
    st.markdown(f"**{title} Worksheet Snapshot**")
    render_metric_row(
        [
            ("Available", available),
            ("Requested", requested),
            ("Used", used),
            ("Unused", unused),
        ],
        4,
    )
    if records:
        worksheet_df = build_currency_df(
            [
                {
                    "Tax Year": row.get("tax_year", ""),
                    "Available": float(row.get("available_amount", 0.0) or 0.0),
                    "Requested": float(row.get("claim_amount", 0.0) or 0.0),
                    "Used": min(float(row.get("available_amount", 0.0) or 0.0), float(row.get("claim_amount", 0.0) or 0.0)),
                }
                for row in records
            ],
            ["Available", "Requested", "Used"],
        )
        st.dataframe(worksheet_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No carryforward rows are entered yet.")
