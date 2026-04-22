import base64
import hashlib
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from guidance import (
    build_eligibility_guidance,
    build_completion_flags,
    build_screening_inputs,
    build_section_progress,
    build_step5_checkpoint_suggestions as step5_build_checkpoint_suggestions,
    build_step5_optimization_preview as step5_build_optimization_preview,
    build_step5_section_statuses as step5_build_section_statuses,
    build_suggestions,
    render_carryforward_mini_worksheet as step5_render_carryforward_mini_worksheet,
    render_step5_optimization_checkpoint as step5_render_optimization_checkpoint,
    render_step5_section_intro as step5_render_section_intro,
    SuggestionItem,
)
from diagnostics import (
    build_filing_readiness_df,
    build_results_quick_notes,
    collect_diagnostics,
    collect_postcalc_diagnostics,
    render_diagnostics_panel,
)
from eligibility import (
    build_eligibility_decision,
)
from results import (
    build_assumptions_overrides_df,
    build_client_key_drivers_df,
    build_client_summary_df,
    build_return_memo_html as results_build_return_memo_html,
    build_missing_support_df,
    build_on428_part_c_df,
    build_on428a_lift_df,
    build_printable_client_summary_html,
    build_printable_client_summary_pdf,
    build_provincial_worksheet_df,
    build_return_package_df,
    build_schedule_11_df,
    build_schedule_3_df,
    build_slip_reconciliation_df,
    build_special_schedule_df,
    build_summary_df,
    build_t776_df,
    build_federal_net_tax_build_up_df,
    render_advisor_scenario_compare as results_render_advisor_scenario_compare,
    render_tax_optimization_panel as results_render_tax_optimization_panel,
)
from tax_config import AVAILABLE_PROVINCES, AVAILABLE_TAX_YEARS, PROVINCES, TAX_CONFIGS
from tax_engine import calculate_personal_tax_return
from tax_engine.constants import FEDERAL_MEDICAL_THRESHOLDS
from tax_engine.credits import (
    calculate_canada_workers_benefit,
    calculate_cwb_disability_supplement,
    calculate_medical_claim,
    calculate_medical_expense_supplement,
    calculate_payroll_overpayment_refunds,
    calculate_spouse_amount,
)
from tax_engine.utils import calculate_federal_bpa, estimate_employee_cpp_ei
from ui_config import PROVINCIAL_CAREGIVER_HELP

META_TITLE = "Canadian Personal Tax Estimator | Advanced Federal & Provincial Tax Calculator"
META_DESCRIPTION = (
    "Advanced Canadian personal tax estimator with employment, investment and rental "
    "income, common deductions, credits, and refund or balance owing estimates."
)
OG_TITLE = "Canadian Personal Tax Estimator"
OG_DESCRIPTION = (
    "Estimate a more complete Canadian personal income tax return with broader CRA-style income, "
    "deduction, credit, and payment inputs."
)
APP_URL = "https://advtax.contexta.biz/"
OG_IMAGE_URL = "https://advtax.contexta.biz/canadian-income-tax-estimator-og.jpg"
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


def build_input_signature(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


FLOW_STEPS = [
    (1, "Slips"),
    (2, "Property and Capital Schedules"),
    (3, "Income and Investment"),
    (4, "Deductions"),
    (5, "Credits, Carryforwards, and Special Cases"),
    (6, "Payments and Withholdings"),
    (7, "Summary & Pre-Calculation Diagnostics"),
]
SLIP_WIZARD_CONFIGS = [
    {
        "tab": "T4",
        "title": "T4 Slip",
        "key": "t4_wizard",
        "columns": [
            "box14_employment_income",
            "box22_tax_withheld",
            "box16_cpp",
            "box18_ei",
            "box24_ei_insurable_earnings",
            "box26_cpp_pensionable_earnings",
            "box20_rpp",
            "box52_pension_adjustment",
            "box44_union_dues",
        ],
        "fields": [
            {"id": "box14_employment_income", "label": "Box 14 Employment Income (example: 65000)", "step": 100.0},
            {"id": "box22_tax_withheld", "label": "Box 22 Income Tax Deducted (example: 8200)", "step": 100.0},
            {"id": "box16_cpp", "label": "Box 16 CPP Contributions (example: 3867.50)", "step": 10.0},
            {"id": "box18_ei", "label": "Box 18 EI Premiums (example: 1049.12)", "step": 10.0},
            {"id": "box24_ei_insurable_earnings", "label": "Box 24 EI Insurable Earnings", "step": 100.0},
            {"id": "box26_cpp_pensionable_earnings", "label": "Box 26 CPP/QPP Pensionable Earnings", "step": 100.0},
            {"id": "box20_rpp", "label": "Box 20 RPP Contributions", "step": 10.0},
            {"id": "box52_pension_adjustment", "label": "Box 52 Pension Adjustment", "step": 10.0},
            {"id": "box44_union_dues", "label": "Box 44 Union Dues", "step": 10.0},
        ],
    },
    {
        "tab": "T4A",
        "title": "T4A Slip",
        "key": "t4a_wizard",
        "columns": ["box16_pension", "box18_lump_sum", "box22_tax_withheld", "box28_other_income"],
        "fields": [
            {"id": "box16_pension", "label": "Box 16 Pension or Superannuation", "step": 100.0},
            {"id": "box18_lump_sum", "label": "Box 18 Lump-Sum Payment", "step": 100.0},
            {"id": "box22_tax_withheld", "label": "Box 22 Income Tax Deducted", "step": 100.0},
            {"id": "box28_other_income", "label": "Box 28 Other Income", "step": 100.0},
        ],
    },
    {
        "tab": "T5",
        "title": "T5 Slip",
        "key": "t5_wizard",
        "columns": [
            "box13_interest",
            "box15_foreign_income",
            "box16_foreign_tax_paid",
            "box25_eligible_dividends_taxable",
            "box26_eligible_dividend_credit",
            "box11_non_eligible_dividends_taxable",
            "box12_non_eligible_dividend_credit",
        ],
        "fields": [
            {"id": "box13_interest", "label": "Box 13 Interest from Canadian Sources", "step": 10.0},
            {"id": "box15_foreign_income", "label": "Box 15 Foreign Income", "step": 10.0},
            {"id": "box16_foreign_tax_paid", "label": "Box 16 Foreign Tax Paid", "step": 10.0},
            {"id": "box25_eligible_dividends_taxable", "label": "Box 25 Eligible Dividends Taxable Amount", "step": 10.0},
            {"id": "box26_eligible_dividend_credit", "label": "Box 26 Dividend Tax Credit for Eligible Dividends", "step": 10.0},
            {"id": "box11_non_eligible_dividends_taxable", "label": "Box 11 Other Than Eligible Dividends Taxable Amount", "step": 10.0},
            {"id": "box12_non_eligible_dividend_credit", "label": "Box 12 Dividend Tax Credit for Other Than Eligible Dividends", "step": 10.0},
        ],
    },
    {
        "tab": "T3",
        "title": "T3 Slip",
        "key": "t3_wizard",
        "columns": [
            "box21_capital_gains",
            "box31_pension_income",
            "box26_other_income",
            "box25_foreign_income",
            "box34_foreign_tax_paid",
            "box50_eligible_dividends_taxable",
            "box51_eligible_dividend_credit",
            "box32_non_eligible_dividends_taxable",
            "box39_non_eligible_dividend_credit",
        ],
        "fields": [
            {"id": "box21_capital_gains", "label": "Box 21 Capital Gains", "step": 10.0},
            {"id": "box31_pension_income", "label": "Box 31 Pension Income", "step": 10.0},
            {"id": "box26_other_income", "label": "Box 26 Other Income", "step": 10.0},
            {"id": "box25_foreign_income", "label": "Box 25 Foreign Non-Business Income", "step": 10.0},
            {"id": "box34_foreign_tax_paid", "label": "Box 34 Foreign Non-Business Tax Paid", "step": 10.0},
            {"id": "box50_eligible_dividends_taxable", "label": "Box 50 Eligible Dividends Taxable Amount", "step": 10.0},
            {"id": "box51_eligible_dividend_credit", "label": "Box 51 Dividend Tax Credit for Eligible Dividends", "step": 10.0},
            {"id": "box32_non_eligible_dividends_taxable", "label": "Box 32 Other Than Eligible Dividends Taxable Amount", "step": 10.0},
            {"id": "box39_non_eligible_dividend_credit", "label": "Box 39 Dividend Tax Credit for Other Than Eligible Dividends", "step": 10.0},
        ],
    },
    {
        "tab": "T4PS",
        "title": "T4PS Slip",
        "key": "t4ps_wizard",
        "columns": [
            "box24_non_eligible_dividends_actual",
            "box25_non_eligible_dividends_taxable",
            "box26_non_eligible_dividend_credit",
            "box30_eligible_dividends_actual",
            "box31_eligible_dividends_taxable",
            "box32_eligible_dividend_credit",
            "box34_capital_gains_or_losses",
            "box35_other_employment_income",
            "box37_foreign_non_business_income",
            "box41_epsp_contributions",
        ],
        "fields": [
            {"id": "box24_non_eligible_dividends_actual", "label": "Box 24 Actual Amount of Non-Eligible Dividends", "step": 10.0},
            {"id": "box25_non_eligible_dividends_taxable", "label": "Box 25 Taxable Amount of Non-Eligible Dividends", "step": 10.0},
            {"id": "box26_non_eligible_dividend_credit", "label": "Box 26 Dividend Tax Credit for Non-Eligible Dividends", "step": 10.0},
            {"id": "box30_eligible_dividends_actual", "label": "Box 30 Actual Amount of Eligible Dividends", "step": 10.0},
            {"id": "box31_eligible_dividends_taxable", "label": "Box 31 Taxable Amount of Eligible Dividends", "step": 10.0},
            {"id": "box32_eligible_dividend_credit", "label": "Box 32 Dividend Tax Credit for Eligible Dividends", "step": 10.0},
            {"id": "box34_capital_gains_or_losses", "label": "Box 34 Capital Gains or Losses", "step": 10.0},
            {"id": "box35_other_employment_income", "label": "Box 35 Other Employment Income", "step": 10.0},
            {"id": "box37_foreign_non_business_income", "label": "Box 37 Foreign Non-Business Income", "step": 10.0},
            {"id": "box41_epsp_contributions", "label": "Box 41 EPSP Contributions (reference only)", "step": 10.0},
        ],
    },
    {
        "tab": "T2202",
        "title": "T2202 Form",
        "key": "t2202_wizard",
        "columns": [
            "box21_months_part_time",
            "box22_months_full_time",
            "box23_session_tuition",
            "box24_total_months_part_time",
            "box25_total_months_full_time",
            "box26_total_eligible_tuition",
        ],
        "fields": [
            {"id": "box21_months_part_time", "label": "Box 21 Eligible Months Part-Time", "step": 1.0},
            {"id": "box22_months_full_time", "label": "Box 22 Eligible Months Full-Time", "step": 1.0},
            {"id": "box23_session_tuition", "label": "Box 23 Tuition Fees For This Session", "step": 10.0},
            {"id": "box24_total_months_part_time", "label": "Box 24 Total Months Part-Time", "step": 1.0},
            {"id": "box25_total_months_full_time", "label": "Box 25 Total Months Full-Time", "step": 1.0},
            {"id": "box26_total_eligible_tuition", "label": "Box 26 Total Eligible Tuition Fees", "step": 10.0},
        ],
    },
]

SLIP_WIZARD_MICROCOPY = {
    "t4_wizard": {
        "should_fill": "Fill this if you received a T4 from an employer. Most employees mainly need Box 14 and Box 22.",
        "tip": "If a box does not appear on your slip, leave it at 0. Box 20 and Box 44 only matter if they are actually shown.",
    },
    "t4a_wizard": {
        "should_fill": "Fill this if you received a T4A for pension, lump-sum, scholarship, self-employed commission, or other T4A-reported income.",
        "tip": "Many users only need Box 16, Box 18, Box 22, or Box 28. Copy only the boxes printed on your own slip.",
    },
    "t5_wizard": {
        "should_fill": "Fill this if your bank, broker, or investment account issued a T5. Use the taxable dividend amounts exactly as shown on the slip.",
        "tip": "Do not gross up dividend amounts yourself in this tab. The slip already shows the taxable amount the return needs.",
    },
    "t3_wizard": {
        "should_fill": "Fill this if you received a T3 from a trust, mutual fund, ETF, or estate. Many investors only need the dividend, capital gain, or foreign income boxes shown on the slip.",
        "tip": "Use the slip's taxable amounts as printed. Leave other boxes at 0 unless they appear on your T3.",
    },
    "t4ps_wizard": {
        "should_fill": "Fill this if you received a T4PS for employee profit sharing, special dividends, or related investment allocations.",
        "tip": "This slip is less common. If you do not have a T4PS in hand, you can skip this tab.",
    },
    "t2202_wizard": {
        "should_fill": "Fill this if your school issued a T2202 for tuition. Most students only need the months and total eligible tuition boxes shown on the form.",
        "tip": "If you are only claiming a carryforward from a prior year and do not have a current-year T2202, you can usually skip this tab.",
    },
}


def inject_meta_tags():
    components.html(
        f"""
        <script>
            const metaTags = [
                {{ attr: "name", key: "description", value: {META_DESCRIPTION!r} }},
                {{ attr: "property", key: "og:title", value: {OG_TITLE!r} }},
                {{ attr: "property", key: "og:description", value: {OG_DESCRIPTION!r} }},
                {{ attr: "property", key: "og:type", value: "website" }},
                {{ attr: "property", key: "og:url", value: {APP_URL!r} }},
                {{ attr: "property", key: "og:image", value: {OG_IMAGE_URL!r} }},
                {{ attr: "property", key: "og:site_name", value: "Contexta" }},
                {{ attr: "name", key: "twitter:card", value: "summary_large_image" }},
                {{ attr: "name", key: "twitter:title", value: {OG_TITLE!r} }},
                {{ attr: "name", key: "twitter:description", value: {OG_DESCRIPTION!r} }},
                {{ attr: "name", key: "twitter:image", value: {OG_IMAGE_URL!r} }},
            ];

            document.title = {META_TITLE!r};

            metaTags.forEach((tag) => {{
                let element = document.head.querySelector(`meta[${{tag.attr}}="${{tag.key}}"]`);
                if (!element) {{
                    element = document.createElement("meta");
                    element.setAttribute(tag.attr, tag.key);
                    document.head.appendChild(element);
                }}
                element.setAttribute("content", tag.value);
            }});
        </script>
        """,
        height=0,
        width=0,
    )


def number_input(label: str, key: str, step: float = 100.0, help_text: str | None = None) -> float:
    value = float(
        st.number_input(
        label,
        min_value=0.0,
        step=step,
        value=float(st.session_state.get(key, st.session_state.get(f"persist_{key}", 0.0))),
        key=key,
        help=help_text,
        )
    )
    st.session_state[f"persist_{key}"] = value
    return value


def checkbox_input(
    label: str,
    key: str,
    value: bool = False,
    help_text: str | None = None,
    container=None,
) -> bool:
    target = container or st
    checked = bool(
        target.checkbox(
            label,
            value=bool(st.session_state.get(key, st.session_state.get(f"persist_{key}", value))),
            key=key,
            help=help_text,
        )
    )
    st.session_state[f"persist_{key}"] = checked
    return checked


def selectbox_input(
    label: str,
    options: list[str],
    key: str,
    default_value: str,
    help_text: str | None = None,
    container=None,
) -> str:
    target = container or st
    selected_value = str(st.session_state.get(key, st.session_state.get(f"persist_{key}", default_value)))
    if selected_value not in options:
        selected_value = default_value
    selected = str(
        target.selectbox(
            label,
            options,
            index=options.index(selected_value),
            key=key,
            help=help_text,
        )
    )
    st.session_state[f"persist_{key}"] = selected
    return selected


def format_currency(value: float) -> str:
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def wrap_pdf_text(pdf: canvas.Canvas, text: str, max_width: float, font: str = "Helvetica", size: int = 9) -> list[str]:
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdf.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def build_report_pack_pdf(
    result: dict,
    province: str,
    province_name: str,
    readiness_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame,
    assumptions_df: pd.DataFrame,
    missing_support_df: pd.DataFrame,
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    left = 54
    right = width - 54
    top = height - 54
    y = top
    line_height = 15
    section_gap = 10
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    logo_path = Path(__file__).resolve().parent / "contexta_logo.png"
    accent_stroke = (0.85, 0.88, 0.92)
    accent_fill = (0.96, 0.98, 1.0)
    accent_text = (0.3, 0.35, 0.42)

    def draw_footer() -> None:
        pdf.setStrokeColorRGB(*accent_stroke)
        pdf.line(left, 34, right, 34)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(0.4, 0.45, 0.52)
        pdf.drawString(left, 22, "Contexta Tax Estimate Report Pack")
        pdf.drawCentredString(width / 2, 22, f"Page {pdf.getPageNumber()}")
        pdf.drawRightString(right, 22, f"Generated: {generated_at}")
        pdf.setFillColorRGB(0, 0, 0)

    def new_page() -> None:
        nonlocal y
        pdf.showPage()
        y = top
        draw_footer()

    def ensure_space(lines_needed: int = 1) -> None:
        nonlocal y
        if y - (lines_needed * line_height) < 64:
            new_page()

    def write_line(text: str, font: str = "Helvetica", size: int = 10, indent: int = 0) -> None:
        nonlocal y
        ensure_space(1)
        pdf.setFont(font, size)
        pdf.drawString(left + indent, y, str(text))
        y -= line_height

    def write_wrapped_lines(
        text: str,
        max_width: float,
        font: str = "Helvetica",
        size: int = 10,
        indent: int = 0,
    ) -> None:
        nonlocal y
        wrapped_lines = wrap_pdf_text(pdf, text, max_width, font=font, size=size)
        ensure_space(len(wrapped_lines) + 1)
        pdf.setFont(font, size)
        for line in wrapped_lines:
            pdf.drawString(left + indent, y, line)
            y -= line_height

    def write_bullet_lines(title: str, items: list[str]) -> None:
        nonlocal y
        if not items:
            return
        ensure_space(len(items) + 3)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(left, y, title)
        y -= line_height
        pdf.setStrokeColorRGB(*accent_stroke)
        pdf.line(left, y + 6, right, y + 6)
        y -= 6
        for item in items:
            write_wrapped_lines(f"- {item}", right - left - 12, size=10, indent=10)
        y -= section_gap + 8

    def write_summary_cards(
        left_title: str,
        left_items: list[str],
        right_title: str,
        right_items: list[str],
    ) -> None:
        nonlocal y
        left_items = left_items or ["No major review flags identified yet."]
        right_items = right_items or ["No significant overrides or capped paths identified yet."]
        gutter = 16
        box_width = (right - left - gutter) / 2
        positions = [left, left + box_width + gutter]
        max_width = box_width - 24

        def estimate_box_height(items: list[str]) -> int:
            lines_used = 2
            for item in items[:4]:
                lines_used += max(1, len(wrap_pdf_text(pdf, f"- {item}", max_width, font="Helvetica", size=9)))
            return max(76, 24 + (lines_used * line_height))

        box_height = max(estimate_box_height(left_items), estimate_box_height(right_items))
        ensure_space(int(box_height / line_height) + 3)

        for box_left, title, items in [
            (positions[0], left_title, left_items[:4]),
            (positions[1], right_title, right_items[:4]),
        ]:
            pdf.setStrokeColorRGB(*accent_stroke)
            pdf.setFillColorRGB(*accent_fill)
            pdf.roundRect(box_left, y - box_height, box_width, box_height, 10, stroke=1, fill=1)
            pdf.setFont("Helvetica-Bold", 11)
            pdf.setFillColorRGB(0.07, 0.1, 0.15)
            pdf.drawString(box_left + 12, y - 16, title)
            pdf.setStrokeColorRGB(*accent_stroke)
            pdf.line(box_left + 12, y - 22, box_left + box_width - 12, y - 22)
            pdf.setFont("Helvetica", 9)
            pdf.setFillColorRGB(*accent_text)
            text_y = y - 36
            for item in items:
                for line in wrap_pdf_text(pdf, f"- {item}", max_width, font="Helvetica", size=9):
                    pdf.drawString(box_left + 12, text_y, line)
                    text_y -= line_height
            pdf.setFillColorRGB(0, 0, 0)
        y -= box_height + 16

    def write_kv_rows(title: str, rows: list[tuple[str, str]]) -> None:
        nonlocal y
        ensure_space(len(rows) + 3)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(left, y, title)
        y -= line_height
        pdf.setStrokeColorRGB(*accent_stroke)
        pdf.line(left, y + 6, right, y + 6)
        y -= 6
        for label, value in rows:
            ensure_space(1)
            pdf.setFont("Helvetica", 10)
            pdf.drawString(left, y, label)
            pdf.drawRightString(right, y, value)
            y -= line_height
        y -= section_gap + 14

    def write_table_rows(title: str, headers: list[str], rows: list[list[str]]) -> None:
        nonlocal y
        if not rows:
            return
        ensure_space(len(rows) + 6)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(left, y, title)
        y -= line_height
        pdf.setFont("Helvetica-Bold", 9)
        if len(headers) == 4:
            positions = [left, left + 62, left + 148, left + 318]
            widths = [50, 72, 154, 170]
            alignments = ["left", "left", "left", "left"]
        elif len(headers) == 3:
            positions = [left, left + 92, right]
            widths = [72, 280, 80]
            alignments = ["left", "left", "right"]
        else:
            positions = [left]
            widths = [right - left]
            alignments = ["left"]

        for index, header in enumerate(headers):
            if alignments[index] == "right":
                pdf.drawRightString(positions[index], y, header)
            else:
                pdf.drawString(positions[index], y, header)
        y -= line_height
        pdf.setStrokeColorRGB(*accent_stroke)
        pdf.line(left, y + 6, right, y + 6)
        y -= 6
        pdf.setFont("Helvetica", 9)
        for row in rows:
            wrapped_cols = [
                wrap_pdf_text(pdf, str(cell), widths[index], font="Helvetica", size=9)
                for index, cell in enumerate(row[: len(headers)])
            ]
            row_height = max(len(col) for col in wrapped_cols) if wrapped_cols else 1
            ensure_space(row_height + 1)
            start_y = y
            for index, lines in enumerate(wrapped_cols):
                for line_index, line in enumerate(lines):
                    draw_y = start_y - (line_index * line_height)
                    if alignments[index] == "right":
                        pdf.drawRightString(positions[index], draw_y, line)
                    else:
                        pdf.drawString(positions[index], draw_y, line)
            y -= line_height
            y -= (row_height - 1) * line_height
        y -= section_gap + 14

    pdf.setTitle("Tax Estimate Report Pack")
    if logo_path.exists():
        try:
            logo_reader = ImageReader(str(logo_path))
            logo_width, logo_height = logo_reader.getSize()
            scale = min(145 / logo_width, 44 / logo_height)
            draw_width = logo_width * scale
            draw_height = logo_height * scale
            pdf.drawImage(logo_reader, left, y - 10, width=draw_width, height=draw_height, mask="auto")
        except Exception:
            pass
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawRightString(right, y, "Tax Estimate Report Pack")
    divider_y = y - 8
    pdf.setStrokeColorRGB(*accent_stroke)
    pdf.line(left, divider_y, right, divider_y)
    y = divider_y - 12
    write_line(f"Province: {province_name}", "Helvetica", 10)
    write_line(f"Generated on: {generated_at}", "Helvetica", 10)
    y -= section_gap

    report_sections = [
        "Return Overview",
        "Line Summary",
        "Filing-Readiness",
        "Slip Reconciliation",
        "Assumptions / Overrides",
        "Missing Support Checklist",
        "Key Credits And Payments",
    ]
    write_bullet_lines("Pack Contents", report_sections)

    quick_review_items, top_warning_items, top_override_items = build_report_pack_snapshot_lists(
        readiness_df=readiness_df,
        assumptions_df=assumptions_df,
        missing_support_df=missing_support_df,
        reconciliation_df=reconciliation_df,
    )
    write_bullet_lines("Quick Review Snapshot", quick_review_items)

    write_summary_cards(
        "Top Warnings",
        top_warning_items,
        "Top Overrides",
        top_override_items,
    )

    write_kv_rows(
        "Return Overview",
        [
            ("Total income", format_currency(result.get("total_income", 0.0))),
            ("Net income", format_currency(result.get("net_income", 0.0))),
            ("Taxable income", format_currency(result.get("taxable_income", 0.0))),
            ("Federal tax", format_currency(result.get("federal_tax", 0.0))),
            (f"{province_name} tax", format_currency(result.get("provincial_tax", 0.0))),
            ("Total income tax payable", format_currency(result.get("total_payable", 0.0))),
            ("Refund", format_currency(result.get("line_48400_refund", 0.0))),
            ("Balance owing", format_currency(result.get("line_48500_balance_owing", 0.0))),
        ],
    )

    line_df = line_summary_df(result, province_name)
    write_table_rows(
        "Line Summary",
        ["Line", "Description", "Amount"],
        [[str(row["Line"]), str(row["Description"]), str(row["Amount"])] for _, row in line_df.head(14).iterrows()],
    )

    write_table_rows(
        "Filing-Readiness",
        ["Status", "Area", "Checklist Item", "Detail"],
        [
            [str(row["Status"]), str(row["Area"]), str(row["Checklist Item"]), str(row["Detail"])]
            for _, row in readiness_df.iterrows()
        ],
    )

    write_table_rows(
        "Slip Reconciliation",
        ["Group", "Area", "Difference", "Why It Differs"],
        [
            [
                str(row["Group"]),
                str(row["Area"]),
                str(row["Difference"]),
                str(row.get("Explanation", "")),
            ]
            for _, row in reconciliation_df.iterrows()
        ],
    )

    write_table_rows(
        "Assumptions / Overrides",
        ["Area", "Item", "Treatment", "Detail"],
        [
            [str(row["Area"]), str(row["Item"]), str(row["Treatment"]), str(row["Detail"])]
            for _, row in assumptions_df.iterrows()
        ],
    )

    write_table_rows(
        "Missing Support Checklist",
        ["Priority", "Area", "Suggested Support", "Why It Matters"],
        [
            [str(row["Priority"]), str(row["Area"]), str(row["Suggested Support"]), str(row["Why It Matters"])]
            for _, row in missing_support_df.iterrows()
        ],
    )

    write_kv_rows(
        "Key Credits And Payments",
        [
            ("Federal non-refundable credits", format_currency(result.get("federal_non_refundable_credits", 0.0))),
            (f"{province_name} non-refundable credits", format_currency(result.get("provincial_non_refundable_credits", 0.0))),
            ("Refundable credits", format_currency(result.get("refundable_credits", 0.0))),
            ("Income tax withheld", format_currency(result.get("income_tax_withheld", 0.0))),
            ("Instalments and other payments", format_currency(result.get("installments_paid", 0.0) + result.get("other_payments", 0.0))),
        ],
    )

    draw_footer()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def render_metric_row(
    items: list[tuple[str, float]],
    columns_count: int | None = None,
    formatter: callable | None = None,
) -> None:
    if not items:
        return
    if columns_count is None:
        columns_count = len(items)
    if formatter is None:
        formatter = format_currency
    columns = st.columns(columns_count)
    for column, (label, value) in zip(columns, items):
        column.metric(label, formatter(value))


def format_plain_number(value: float) -> str:
    return f"{int(value)}" if float(value).is_integer() else f"{value:.2f}"


PLANNING_PRIORITY_THRESHOLDS = {
    "high_balance_owing": 1500.0,
    "spouse_low_income_upper": 16000.0,
    "material_tuition_room": 1000.0,
    "light_deduction_usage": 5000.0,
}


def build_planning_priority_context(
    result: dict,
    inside_items: list[dict],
    refund_amount: float,
    balance_owing_amount: float,
) -> dict[str, float | bool | set[str]]:
    inside_ids = {str(item.get("id", "")) for item in inside_items}
    spouse_claim_used = float(result.get("line_30300", 0.0))
    spouse_net_income_for_review = float(result.get("spouse_net_income_for_lift", 0.0))
    tuition_available_total = float(result.get("schedule11_total_available", 0.0))
    tuition_claim_used_total = float(result.get("schedule11_total_claim_used", 0.0))
    total_deductions_used = float(result.get("total_deductions", 0.0))
    tuition_unused_total = max(0.0, tuition_available_total - tuition_claim_used_total)

    has_spouse_signal = "spouse_amount" in inside_ids or spouse_claim_used > 0
    has_household_signal = (
        "household_dependants" in inside_ids
        or result.get("line_30400", 0.0) > 0
        or result.get("caregiver_amount_claim", 0.0) > 0
    )
    has_tuition_signal = "tuition_and_student" in inside_ids or tuition_claim_used_total > 0
    has_low_income_signal = (
        "low_income_refundable" in inside_ids
        or result.get("canada_workers_benefit", 0.0) > 0
        or result.get("medical_expense_supplement", 0.0) > 0
    )
    has_deduction_signal = "deductions_review" in inside_ids or total_deductions_used > 0
    has_medical_donation_signal = (
        "medical_and_donations" in inside_ids
        or result.get("schedule9_total_regular_donations_claimed", 0.0) > 0
        or result.get("federal_donation_credit", 0.0) > 0
    )
    has_foreign_signal = (
        "foreign_and_investment" in inside_ids
        or result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0) > 0
    )

    return {
        "inside_ids": inside_ids,
        "refund_amount": refund_amount,
        "balance_owing_amount": balance_owing_amount,
        "has_spouse_signal": has_spouse_signal,
        "has_household_signal": has_household_signal,
        "has_tuition_signal": has_tuition_signal,
        "has_low_income_signal": has_low_income_signal,
        "has_deduction_signal": has_deduction_signal,
        "has_medical_donation_signal": has_medical_donation_signal,
        "has_foreign_signal": has_foreign_signal,
        "spouse_claim_used": spouse_claim_used,
        "spouse_net_income_for_review": spouse_net_income_for_review,
        "tuition_available_total": tuition_available_total,
        "tuition_claim_used_total": tuition_claim_used_total,
        "tuition_unused_total": tuition_unused_total,
        "total_deductions_used": total_deductions_used,
        "high_balance_owing": balance_owing_amount >= PLANNING_PRIORITY_THRESHOLDS["high_balance_owing"],
        "spouse_amount_not_used_but_may_be_available": (
            has_spouse_signal
            and spouse_claim_used <= 0.0
            and spouse_net_income_for_review > 0.0
            and spouse_net_income_for_review < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]
        ),
        "material_tuition_room_remaining": (
            has_tuition_signal and tuition_unused_total >= PLANNING_PRIORITY_THRESHOLDS["material_tuition_room"]
        ),
    }


def planning_priority(
    base: int,
    context: dict[str, float | bool | set[str]],
    *,
    spouse: bool = False,
    household: bool = False,
    tuition: bool = False,
    low_income: bool = False,
    deduction: bool = False,
    medical_donation: bool = False,
    foreign: bool = False,
) -> int:
    priority = base
    balance_owing_amount = float(context["balance_owing_amount"])
    refund_amount = float(context["refund_amount"])
    high_balance_owing = bool(context["high_balance_owing"])

    if balance_owing_amount > 0:
        if deduction:
            priority -= 8
        if spouse or household or tuition or medical_donation or low_income:
            priority -= 5
    if high_balance_owing:
        if deduction:
            priority -= 10
        if spouse or household or tuition or medical_donation:
            priority -= 6
    if refund_amount > 0:
        if spouse or household or tuition:
            priority -= 3
        if foreign:
            priority += 4
    if spouse and bool(context["has_spouse_signal"]):
        priority -= 10
    if spouse and bool(context["spouse_amount_not_used_but_may_be_available"]):
        priority -= 12
    if household and bool(context["has_household_signal"]):
        priority -= 6
    if tuition and bool(context["has_tuition_signal"]):
        priority -= 8
    if tuition and bool(context["material_tuition_room_remaining"]):
        priority -= 12
    if low_income and bool(context["has_low_income_signal"]):
        priority -= 7
    if deduction and bool(context["has_deduction_signal"]):
        priority -= 6
    if deduction and high_balance_owing and float(context["total_deductions_used"]) < PLANNING_PRIORITY_THRESHOLDS["light_deduction_usage"]:
        priority -= 6
    if medical_donation and bool(context["has_medical_donation_signal"]):
        priority -= 4
    if foreign and bool(context["has_foreign_signal"]):
        priority -= 2
    return priority


def build_tax_optimization_items(
    result: dict,
    suggestions: "list[SuggestionItem] | None" = None,
) -> list[tuple[str, str]]:
    suggestions = suggestions or []
    items: list[tuple[int, str, str]] = []

    def add_item(priority: int, title: str, body: str) -> None:
        items.append((priority, title, body))

    spouse_net_income = float(result.get("spouse_net_income_for_lift", 0.0))
    spouse_claim_used = float(result.get("line_30300", 0.0))
    tuition_available = float(result.get("schedule11_total_available", 0.0))
    tuition_claimed = float(result.get("schedule11_total_claim_used", 0.0))
    tuition_unused = max(0.0, tuition_available - tuition_claimed)
    balance_owing = float(result.get("line_48500_balance_owing", 0.0))
    refund_amount = float(result.get("line_48400_refund", 0.0))
    total_deductions = float(result.get("total_deductions", 0.0))
    cwb_amount = float(result.get("canada_workers_benefit", 0.0))
    donation_amount = max(
        float(result.get("schedule9_total_regular_donations_claimed", 0.0)),
        float(result.get("federal_donation_credit", 0.0)),
    )
    foreign_credit_amount = float(result.get("federal_foreign_tax_credit", 0.0)) + float(result.get("provincial_foreign_tax_credit", 0.0))
    spouse_signal = any(str(item.get("id", "")) == "spouse_amount" for item in suggestions)
    tuition_signal = any(str(item.get("id", "")) == "tuition_and_student" for item in suggestions)
    deduction_signal = any(str(item.get("id", "")) == "deductions_review" for item in suggestions)
    medical_donation_signal = any(str(item.get("id", "")) == "medical_and_donations" for item in suggestions)
    foreign_signal = any(str(item.get("id", "")) == "foreign_and_investment" for item in suggestions)
    low_income_signal = any(str(item.get("id", "")) == "low_income_refundable" for item in suggestions)

    if spouse_signal and spouse_claim_used <= 0.0 and spouse_net_income > 0.0 and spouse_net_income < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]:
        add_item(
            10,
            "Possible spouse amount review",
            "On the facts entered so far, spouse amount may still be supportable if your spouse or partner had low net income at year end and that position has not yet been fully worked through.",
        )
    if tuition_signal and tuition_unused >= PLANNING_PRIORITY_THRESHOLDS["material_tuition_room"]:
        add_item(
            20,
            "Unused tuition room still showing",
            f"The file is still showing about {format_currency(tuition_unused)} of tuition room unused, so a Schedule 11 or carryforward review may still improve the current filing position.",
        )
    if deduction_signal and balance_owing >= PLANNING_PRIORITY_THRESHOLDS["high_balance_owing"] and total_deductions < PLANNING_PRIORITY_THRESHOLDS["light_deduction_usage"]:
        add_item(
            30,
            "Deduction review may still reduce the balance owing",
            "The balance owing remains material relative to the deductions entered, so RRSP, FHSA, child care, moving, support, or work-related deductions may still be worth reviewing before filing.",
        )
    if low_income_signal and cwb_amount <= 0.0:
        add_item(
            40,
            "Refundable support may still be worth checking",
            "Based on the current income picture, Canada Workers Benefit, the disability supplement path, or the Medical Expense Supplement may still be relevant on this file.",
        )
    if medical_donation_signal and donation_amount <= 0.0:
        add_item(
            50,
            "Medical or donation credits may still be underused",
            "Medical expenses or charitable donations may still create non-refundable credits if those amounts have not yet been fully worked through.",
        )
    if foreign_signal and foreign_credit_amount <= 0.0 and refund_amount <= 0.0:
        add_item(
            60,
            "Foreign tax inputs may still need positioning",
            "If foreign income or tax paid was entered elsewhere but not fully matched here, the foreign credit position may still change the return outcome.",
        )

    items.sort(key=lambda row: row[0])
    return [(title, body) for _, title, body in items[:3]]


def build_tax_optimization_memo(
    result: dict,
    suggestions: "list[SuggestionItem] | None" = None,
) -> tuple[str, list[tuple[str, str]]]:
    items = build_tax_optimization_items(result, suggestions)
    balance_owing = float(result.get("line_48500_balance_owing", 0.0))

    if balance_owing > 0:
        lead = (
            "Preparer note: before treating the current balance owing as final, review the strongest remaining deduction, household, and carryforward positions first."
        )
    else:
        lead = ""

    return lead, items[:2]


def render_tax_optimization_panel(result: dict, suggestions: "list[SuggestionItem] | None" = None) -> None:
    lead, items = build_tax_optimization_memo(result, suggestions)
    if not items and not lead:
        return
    with st.container(border=True):
        st.markdown("##### Potential Tax Savings")
        if lead:
            st.caption(lead)
        for heading, body in items:
            st.markdown(f"- **{heading}**: {body}")


def render_step5_optimization_checkpoint(
    result_preview: dict,
    suggestions: "list[SuggestionItem] | None" = None,
) -> None:
    items = build_tax_optimization_items(result_preview, suggestions)
    if not items:
        return

    short_bodies = {
        "Possible spouse amount review": "Check spouse net income and whether line 30300 should be worked through here.",
        "Unused tuition room still showing": "Review available tuition, requested amount, and any carryforward before leaving Step 5.",
        "Deduction review may still reduce the balance owing": "If tax is still high, review RRSP, FHSA, child care, moving, support, and work deductions first.",
        "Refundable support may still be worth checking": "Confirm whether CWB, the disability supplement path, or the medical expense supplement should be opened.",
        "Medical or donation credits may still be underused": "Open this only if medical expenses or donations were not fully entered yet.",
        "Foreign tax inputs may still need positioning": "Recheck foreign income and tax paid only if those amounts apply on this return.",
    }

    with st.container(border=True):
        st.markdown("##### Optimization Checkpoint")
        st.caption("Before you continue, here is what looks most worth your time in this step based on what is already entered.")
        for title, body in items[:3]:
            st.markdown(f"- **{title}**: {short_bodies.get(title, body)}")


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

    statuses: dict[str, dict[str, str]] = {
        "common_credits": {
            "status": "Probably skip",
            "why": "Open this if you paid tuition, student loan interest, medical expenses, or donations, or if a common non-refundable claim still needs input.",
            "note": "Nothing obvious is standing out yet from the current Step 5 entries.",
        },
        "household": {
            "status": "Probably skip",
            "why": "Open this if spouse, dependant, caregiver, support, or disability-transfer facts could change which household claim is supportable.",
            "note": "No household facts are standing out yet from the current inputs.",
        },
        "manual_overrides": {
            "status": "Probably skip",
            "why": "Open this only if you already have a worksheet amount or need to override the auto estimate.",
            "note": "For most returns, this can stay closed.",
        },
        "refundable": {
            "status": "Probably skip",
            "why": "Open this if lower-income support, CWB, training credit, or the medical expense supplement could still change the result.",
            "note": "No refundable-credit signal is standing out yet.",
        },
        "foreign": {
            "status": "Probably skip",
            "why": "Open this only if foreign income, foreign tax paid, or a manual dividend-credit override still needs review.",
            "note": "If slips already covered the amounts, this section can usually stay closed.",
        },
        "carryforwards": {
            "status": "Probably skip",
            "why": "Open this if you are bringing forward tuition, donation, or province-specific amounts from a prior year.",
            "note": "No carryforward signal is standing out yet.",
        },
        "province_special": {
            "status": "Review if applicable",
            "why": f"Open this only if a {province_name} worksheet, special schedule, or province-specific credit clearly applies.",
            "note": "This is usually only relevant for special provincial cases.",
        },
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
    badge_styles = {
        "Already active": {"bg": "rgba(38, 137, 83, 0.18)", "fg": "#9EE6BE", "border": "rgba(38, 137, 83, 0.28)"},
        "Looks underused": {"bg": "rgba(94, 166, 255, 0.16)", "fg": "#D8E9FF", "border": "rgba(94, 166, 255, 0.28)"},
        "Probably skip": {"bg": "rgba(143, 168, 198, 0.12)", "fg": "#B8C7D9", "border": "rgba(143, 168, 198, 0.18)"},
        "Review if applicable": {"bg": "rgba(192, 144, 60, 0.16)", "fg": "#F0D8A3", "border": "rgba(192, 144, 60, 0.24)"},
    }
    style = badge_styles.get(section["status"], badge_styles["Review if applicable"])
    st.markdown(
        (
            "<div style='border:1px solid rgba(255,255,255,0.08);border-radius:14px;"
            "padding:12px 14px;margin:8px 0 14px 0;background:#101826;'>"
            "<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;'>"
            f"<span style='display:inline-block;padding:4px 10px;border-radius:999px;background:{style['bg']};"
            f"color:{style['fg']};border:1px solid {style['border']};font-size:0.74rem;font-weight:700;"
            f"letter-spacing:0.04em;text-transform:uppercase;'>{section['status']}</span>"
            "</div>"
            f"<div style='color:#D9E3F0;font-size:0.93rem;line-height:1.55;margin-bottom:6px;'><strong>Why this matters now:</strong> {section['why']}</div>"
            f"<div style='color:#9FB2C9;font-size:0.90rem;line-height:1.5;'>{section['note']}</div>"
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


def render_carryforward_mini_worksheet(title: str, records: list[dict[str, object]]) -> None:
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


def build_advisor_summary_sections(
    result: dict,
    readiness_df: pd.DataFrame,
    suggestions: "list[SuggestionItem] | None" = None,
) -> list[tuple[str, list[str]]]:
    suggestions = suggestions or []
    refund_amount = float(result.get("line_48400_refund", 0.0))
    balance_owing_amount = float(result.get("line_48500_balance_owing", 0.0))
    inside_items = [
        item for item in suggestions
        if "outside this estimator" not in item["where"].lower()
    ]
    outside_items = [
        item for item in suggestions
        if "outside this estimator" in item["where"].lower()
    ]

    ranked_opportunities: list[tuple[int, str, bool, frozenset[str]]] = []
    estimate_changers: list[str] = []
    verify_items: list[str] = []
    planning_context = build_planning_priority_context(
        result=result,
        inside_items=inside_items,
        refund_amount=refund_amount,
        balance_owing_amount=balance_owing_amount,
    )
    inside_ids = planning_context["inside_ids"]
    claim_specific_opportunity_ids: set[str] = set()

    def infer_topics(text: str) -> frozenset[str]:
        lowered = text.lower()
        topics: set[str] = set()
        if any(token in lowered for token in ["spouse", "common-law"]):
            topics.add("spouse")
        if any(token in lowered for token in ["dependant", "caregiver", "disability transfer", "medical claim"]):
            topics.add("household")
        if any(token in lowered for token in ["tuition", "student loan", "carryforward"]):
            topics.add("tuition")
        if any(token in lowered for token in ["medical expenses", "charitable donations", "donation"]):
            topics.add("medical_donation")
        if any(token in lowered for token in ["rrsp", "fhsa", "moving expenses", "child care", "support payments", "work-related deductions", "deductions"]):
            topics.add("deduction")
        if any(token in lowered for token in ["foreign income", "dividend", "foreign tax"]):
            topics.add("foreign")
        if any(token in lowered for token in ["canada workers benefit", "medical expense supplement", "lower-income"]):
            topics.add("low_income")
        if not topics:
            topics.add("generic")
        return frozenset(topics)

    def add_opportunity(priority: int, text: str, *, generic: bool = False) -> None:
        ranked_opportunities.append((priority, text, generic, infer_topics(text)))

    # Prefer claim-level planning notes over generic review language.
    if any(item.get("id") == "spouse_amount" for item in inside_items):
        claim_specific_opportunity_ids.add("spouse_amount")
        add_opportunity(
            planning_priority(18, planning_context, spouse=True),
            "Claim opportunity: spouse or common-law partner amount may still be available if spouse net income was low. Check Step 5 -> Household And Dependants."
        )
    if any(item.get("id") == "household_dependants" for item in inside_items):
        claim_specific_opportunity_ids.add("household_dependants")
        add_opportunity(
            planning_priority(24, planning_context, household=True),
            "Claim opportunity: an eligible dependant, caregiver, disability transfer, or dependant-medical claim may still be available. Check Step 5 -> Household And Dependants."
        )
    if any(item.get("id") == "medical_and_donations" for item in inside_items):
        claim_specific_opportunity_ids.add("medical_and_donations")
        add_opportunity(
            planning_priority(34, planning_context, medical_donation=True),
            "Claim opportunity: medical expenses or donations may still add credits if not fully entered. Check Step 5 -> Common Credits And Claim Amounts."
        )
    if any(item.get("id") == "deductions_review" for item in inside_items):
        claim_specific_opportunity_ids.add("deductions_review")
        add_opportunity(
            planning_priority(16, planning_context, deduction=True),
            "Claim opportunity: RRSP, FHSA, child care, moving, support, or work deductions may still improve the return. Check Step 4 -> Deductions."
        )
    if any(item.get("id") == "foreign_and_investment" for item in inside_items):
        claim_specific_opportunity_ids.add("foreign_and_investment")
        add_opportunity(
            planning_priority(50, planning_context, foreign=True),
            "Claim opportunity: foreign income, dividend classification, or foreign tax credits may still change the result. Check Step 3 -> Income And Investment and Step 5 -> Foreign Tax And Dividend Credits."
        )
    if any(item.get("id") == "low_income_refundable" for item in inside_items):
        claim_specific_opportunity_ids.add("low_income_refundable")
        add_opportunity(
            planning_priority(38, planning_context, low_income=True),
            "Claim opportunity: CWB, the disability supplement path, or the medical expense supplement may still apply. Check Step 5 -> Refundable Credits."
        )

    for item in inside_items:
        item_id = str(item.get("id", ""))
        if item_id in claim_specific_opportunity_ids:
            continue
        review_line = (
            f"Review-only item: {item['label'].rstrip('.')} may still need a final check. Review {item['where']}."
        )
        if len(ranked_opportunities) < 7:
            add_opportunity(planning_priority(90, planning_context), review_line, generic=True)
        if any(
            token in f"{item['label']} {item['reason']}".lower()
            for token in ["foreign", "dividend", "tuition", "carryforward", "household", "spouse", "dependant", "deduction", "credit"]
        ) and len(estimate_changers) < 3:
            estimate_changers.append(
                f"Review-only item: {item['label'].rstrip('.')} remains a higher-impact review area. {item['reason']}"
            )

    if result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0) > 0:
        estimate_changers.append(
            "Review-only item: foreign tax credits are active, so source classification, slip support, and the T2209/T2036 ceiling should be confirmed."
        )
    if result.get("schedule11_total_claim_used", 0.0) > 0:
        estimate_changers.append(
            "Review-only item: tuition is active, so available balances, transfer positioning, and carryforward treatment should be confirmed."
        )
    if result.get("schedule9_total_regular_donations_claimed", 0.0) > 0:
        estimate_changers.append(
            "Review-only item: donation claims are active, so receipt support, carryforward room, and net-income limits should be confirmed."
        )
    if result.get("line_30300", 0.0) > 0 or result.get("line_30400", 0.0) > 0 or result.get("caregiver_amount_claim", 0.0) > 0:
        estimate_changers.append(
            "Review-only item: household claims are active, so support, custody, living arrangements, and dependant net income should be rechecked."
        )
    if result.get("income_tax_withheld", 0.0) > 0 and balance_owing_amount > 0:
        estimate_changers.append(
            "Review-only item: a balance owing still remains even with withholding entered, so deductions, credits, or support details may still move payable."
        )
    if result.get("income_tax_withheld", 0.0) > 0 and refund_amount > 0:
        estimate_changers.append(
            "Review-only item: the current refund appears to be supported in part by withholding, so any later claim change will likely change the amount of refund."
        )

    if not readiness_df.empty:
        missing_rows = readiness_df[readiness_df["Status"].astype(str) == "Missing"]
        review_rows = readiness_df[readiness_df["Status"].astype(str) == "Review"]
        for _, row in missing_rows.head(2).iterrows():
            verify_items.append(
                f"Support still missing: {row['Area']} - {row['Checklist Item']}."
            )
        for _, row in review_rows.head(2).iterrows():
            verify_items.append(
                f"Needs final review: {row['Area']} - {row['Checklist Item']}."
            )

    for item in outside_items[:2]:
        verify_items.append(
            f"Outside-estimator follow-up: {item['label']} {item['reason']}"
        )

    def dedupe_keep_order(items: list[str], limit: int = 3) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for entry in items:
            key = entry.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
            if len(ordered) >= limit:
                break
        return ordered

    estimate_changers = dedupe_keep_order(estimate_changers)
    verify_items = dedupe_keep_order(verify_items)

    sensitivity_topics: set[str] = set()
    for line in estimate_changers:
        sensitivity_topics.update(infer_topics(line))

    ranked_opportunities.sort(key=lambda item: item[0])
    selected_opportunities: list[str] = []
    selected_topic_sets: list[frozenset[str]] = []
    generic_count = 0

    non_generic_candidates = [item for item in ranked_opportunities if not item[2]]
    if non_generic_candidates:
        first_priority, first_text, first_is_generic, first_topics = non_generic_candidates[0]
        selected_opportunities.append(first_text)
        selected_topic_sets.append(first_topics)
        if first_is_generic:
            generic_count += 1

    for priority, text, is_generic, topics in ranked_opportunities:
        if text in selected_opportunities:
            continue
        if len(selected_opportunities) >= 3:
            break
        if is_generic and generic_count >= 1:
            continue
        if topics & sensitivity_topics:
            continue
        if any(topics & existing for existing in selected_topic_sets):
            continue
        selected_opportunities.append(text)
        selected_topic_sets.append(topics)
        if is_generic:
            generic_count += 1

    for priority, text, is_generic, topics in ranked_opportunities:
        if text in selected_opportunities:
            continue
        if len(selected_opportunities) >= 3:
            break
        if is_generic and generic_count >= 1:
            continue
        if any(topics & existing for existing in selected_topic_sets):
            continue
        selected_opportunities.append(text)
        selected_topic_sets.append(topics)
        if is_generic:
            generic_count += 1

    opportunities = dedupe_keep_order(selected_opportunities, limit=3)

    if not opportunities:
        opportunities = [
            "Claim opportunity: no obvious missed claim is standing out yet, but deductions, credits, and household positions should still be checked before filing."
        ]
    if not estimate_changers:
        estimate_changers = [
            "Review-only item: withholding, deduction support, credit eligibility, and carryforward treatment remain the main variables that could move the result."
        ]
    if not verify_items:
        verify_items = [
            "Confirm slip totals, major deduction support, and any credit or carryforward amounts before relying on this estimate."
        ]

    return [
        ("Claim Opportunities", opportunities),
        ("Review-Only Items", estimate_changers),
        ("Verification", verify_items),
    ]


def build_advisor_summary_lead(result: dict, *, include_outcome: bool = True) -> str:
    refund_amount = float(result.get("line_48400_refund", 0.0))
    balance_owing_amount = float(result.get("line_48500_balance_owing", 0.0))
    deductions = float(result.get("total_deductions", 0.0))
    refundable_credits = float(result.get("refundable_credits", 0.0))
    withholding = float(result.get("income_tax_withheld", 0.0))

    if refund_amount > 0:
        outcome = f"Estimated refund: {format_currency(refund_amount)}."
    elif balance_owing_amount > 0:
        outcome = f"Estimated balance owing: {format_currency(balance_owing_amount)}."
    else:
        outcome = "Estimated result: close to break-even."

    drivers: list[str] = []
    if withholding > 0:
        drivers.append("withholding already entered")
    if deductions > 0:
        drivers.append("deductions currently claimed")
    if refundable_credits > 0:
        drivers.append("refundable credits in the estimate")

    if drivers:
        driver_text = ", ".join(drivers[:-1]) + (f", and {drivers[-1]}" if len(drivers) > 1 else drivers[0])
        body = (
            f"The current position appears to be driven mainly by {driver_text}. "
            "The notes below highlight where the file may still move or need support."
        )
    else:
        body = (
            "The next check is whether all available deductions, credits, and household positions "
            "have actually been worked through."
        )

    return f"{outcome} {body}" if include_outcome else body


def build_return_memo_html(result: dict) -> str:
    memo_text = build_advisor_summary_lead(result, include_outcome=True)
    highlight_style = (
        "display:inline-block;padding:1px 8px 2px 8px;border-radius:999px;"
        "background:rgba(94, 166, 255, 0.14);border:1px solid rgba(94, 166, 255, 0.22);"
        "color:#F2F7FF;font-weight:700;letter-spacing:0.01em;"
    )

    if result.get("line_48400_refund", 0.0) > 0:
        amount_text = format_currency(result["line_48400_refund"])
        memo_text = memo_text.replace(amount_text, f"<span style='{highlight_style}'>{amount_text}</span>", 1)
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        amount_text = format_currency(result["line_48500_balance_owing"])
        memo_text = memo_text.replace(amount_text, f"<span style='{highlight_style}'>{amount_text}</span>", 1)

    return memo_text


def format_result_outcome_chip(result: dict) -> str:
    refund_amount = float(result.get("line_48400_refund", 0.0))
    balance_owing_amount = float(result.get("line_48500_balance_owing", 0.0))
    if refund_amount > 0:
        return f"Refund {format_currency(refund_amount)}"
    if balance_owing_amount > 0:
        return f"Balance owing {format_currency(balance_owing_amount)}"
    return "Near break-even"


def scenario_improvement_value(current_result: dict, scenario_result: dict) -> float:
    current_refund = float(current_result.get("line_48400_refund", 0.0))
    current_balance = float(current_result.get("line_48500_balance_owing", 0.0))
    scenario_refund = float(scenario_result.get("line_48400_refund", 0.0))
    scenario_balance = float(scenario_result.get("line_48500_balance_owing", 0.0))
    return (scenario_refund - current_refund) + (current_balance - scenario_balance)


def format_scenario_delta(current_result: dict, scenario_result: dict) -> str:
    delta = scenario_improvement_value(current_result, scenario_result)
    if abs(delta) < 0.005:
        return "No meaningful change"
    if delta > 0:
        if float(current_result.get("line_48500_balance_owing", 0.0)) > 0 or float(scenario_result.get("line_48500_balance_owing", 0.0)) > 0:
            return f"Improves by about {format_currency(delta)}"
        return f"Increases refund by about {format_currency(delta)}"
    if float(current_result.get("line_48400_refund", 0.0)) > 0:
        return f"Reduces refund by about {format_currency(abs(delta))}"
    return f"Worsens by about {format_currency(abs(delta))}"


def build_advisor_summary_scenarios(current_result: dict, calculation_inputs: dict | None) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = [
        {
            "title": "Current Return",
            "outcome": format_result_outcome_chip(current_result),
            "delta": "Current filed position",
            "note": "Based on the inputs currently entered.",
        }
    ]
    if not calculation_inputs:
        return cards + [
            {
                "title": "With spouse amount",
                "outcome": "No clear additional benefit",
                "delta": "No clear additional benefit on current facts",
                "note": "Add spouse facts first if you want to compare this scenario.",
            },
            {
                "title": "With tuition review",
                "outcome": "No clear additional benefit",
                "delta": "No clear additional benefit on current facts",
                "note": "Add tuition, carryforward, or student-loan inputs first if you want to compare this scenario.",
            },
            {
                "title": "With deduction cleanup",
                "outcome": "No clear additional benefit",
                "delta": "No clear additional benefit on current facts",
                "note": "Add deduction signals first if you want to compare this scenario.",
            },
        ]

    scenario_map: dict[str, dict[str, str]] = {}

    def set_default_scenario(title: str, note: str) -> None:
        scenario_map[title] = {
            "title": title,
            "outcome": "No clear additional benefit",
            "delta": "No clear additional benefit on current facts",
            "note": note,
        }

    def try_add_scenario(title: str, note: str, updates: dict[str, float | bool]) -> None:
        scenario_inputs = dict(calculation_inputs)
        scenario_inputs.update(updates)
        scenario_result = calculate_personal_tax_return(scenario_inputs)
        scenario_map[title] = {
            "title": title,
            "outcome": format_result_outcome_chip(scenario_result),
            "delta": format_scenario_delta(current_result, scenario_result),
            "note": note,
        }

    spouse_net_income = float(calculation_inputs.get("spouse_net_income", 0.0))
    set_default_scenario(
        "With spouse amount",
        "No spouse review opportunity is standing out yet from the current facts entered.",
    )
    if (
        bool(calculation_inputs.get("has_spouse_end_of_year", False))
        and (
            float(current_result.get("line_30300", 0.0)) <= 0.0
            or spouse_net_income < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]
        )
    ):
        try_add_scenario(
            "With spouse amount",
            "Assumes spouse amount review is completed using the spouse facts already entered.",
            {
                "spouse_claim_enabled": True,
                "spouse_amount_claim": 0.0,
            },
        )

    current_year_tuition_available = float(current_result.get("schedule11_current_year_tuition_available", 0.0))
    tuition_carryforward_available = float(current_result.get("schedule11_carryforward_available", 0.0))
    current_year_requested = float(calculation_inputs.get("schedule11_current_year_claim_requested", 0.0))
    carryforward_requested = float(calculation_inputs.get("schedule11_carryforward_claim_requested", 0.0))
    set_default_scenario(
        "With tuition review",
        "No material tuition, carryforward, or student-loan review signal is standing out yet.",
    )
    if (
        current_year_tuition_available > 0.0
        or tuition_carryforward_available > 0.0
        or float(calculation_inputs.get("student_loan_interest", 0.0)) > 0.0
    ):
        try_add_scenario(
            "With tuition review",
            "Assumes available tuition and carryforward amounts are fully reviewed and positioned.",
            {
                "tuition_amount_claim": current_year_tuition_available,
                "schedule11_current_year_claim_requested": current_year_tuition_available,
                "schedule11_carryforward_claim_requested": tuition_carryforward_available,
            },
        )

    balance_owing = float(current_result.get("line_48500_balance_owing", 0.0))
    employment_income = float(calculation_inputs.get("employment_income", 0.0))
    deduction_candidates = [
        {
            "key": "rrsp_deduction",
            "label": "RRSP deduction review",
            "note_template": "Assumes about {amount} of additional RRSP deduction becomes supportable after a final review.",
            "priority": 1,
        },
        {
            "key": "fhsa_deduction",
            "label": "FHSA deduction review",
            "note_template": "Assumes about {amount} of additional FHSA deduction becomes supportable after a final review.",
            "priority": 2,
        },
        {
            "key": "child_care_expenses",
            "label": "child care review",
            "note_template": "Assumes about {amount} of additional child care expenses become supportable after a final review.",
            "priority": 3,
        },
        {
            "key": "moving_expenses",
            "label": "moving-expense review",
            "note_template": "Assumes about {amount} of additional moving expenses become supportable after a final review.",
            "priority": 4,
        },
        {
            "key": "support_payments_deduction",
            "label": "support-deduction review",
            "note_template": "Assumes about {amount} of additional support deduction becomes supportable after a final review.",
            "priority": 5,
        },
        {
            "key": "carrying_charges",
            "label": "carrying-charge review",
            "note_template": "Assumes about {amount} of additional carrying charges become supportable after a final review.",
            "priority": 6,
        },
        {
            "key": "other_employment_expenses",
            "label": "employment-expense review",
            "note_template": "Assumes about {amount} of additional employment expenses become supportable after a final review.",
            "priority": 7,
        },
        {
            "key": "other_deductions",
            "label": "other deduction review",
            "note_template": "Assumes about {amount} of additional deductions become supportable after a final review.",
            "priority": 8,
        },
    ]
    total_deductions = sum(float(calculation_inputs.get(item["key"], 0.0)) for item in deduction_candidates)
    set_default_scenario(
        "With deduction cleanup",
        "No strong deduction-cleanup opportunity is standing out yet from the current inputs.",
    )
    if (balance_owing > 0.0 or (employment_income > 0.0 and total_deductions < max(2500.0, employment_income * 0.06))) and employment_income > 0.0:
        cleanup_amount = min(3000.0, max(1000.0, employment_income * 0.03))
        populated_candidates = [
            item for item in deduction_candidates if float(calculation_inputs.get(item["key"], 0.0)) > 0.0
        ]
        if populated_candidates:
            selected_candidate = sorted(
                populated_candidates,
                key=lambda item: (-float(calculation_inputs.get(item["key"], 0.0)), item["priority"]),
            )[0]
        else:
            selected_candidate = deduction_candidates[0]
        try_add_scenario(
            "With deduction cleanup",
            selected_candidate["note_template"].format(amount=format_currency(cleanup_amount)),
            {
                selected_candidate["key"]: float(calculation_inputs.get(selected_candidate["key"], 0.0)) + cleanup_amount,
            },
        )

    cards.extend(
        [
            scenario_map["With spouse amount"],
            scenario_map["With tuition review"],
            scenario_map["With deduction cleanup"],
        ]
    )
    return cards[:4]


def render_advisor_scenario_compare(current_result: dict, calculation_inputs: dict | None) -> None:
    scenario_cards = build_advisor_summary_scenarios(current_result, calculation_inputs)
    with st.container():
        st.markdown("##### Scenario Compare")
        columns = st.columns(len(scenario_cards))
        for column, card in zip(columns, scenario_cards):
            with column:
                st.markdown(
                    (
                        "<div style='background:#101826;border:1px solid rgba(255,255,255,0.08);"
                        "border-radius:16px;padding:14px 15px 15px 15px;min-height:178px;margin:0 0 14px 0;'>"
                        f"<div style='font-size:0.78rem;letter-spacing:0.06em;text-transform:uppercase;color:#8FA8C6;font-weight:700;margin-bottom:8px;'>{card['title']}</div>"
                        f"<div style='color:#F2F7FF;font-weight:700;font-size:1.02rem;line-height:1.4;margin-bottom:8px;'>{card['outcome']}</div>"
                        f"<div style='display:inline-block;padding:4px 10px;border-radius:999px;background:rgba(94, 166, 255, 0.12);"
                        f"color:#D8E9FF;border:1px solid rgba(94, 166, 255, 0.18);font-size:0.78rem;font-weight:700;margin-bottom:10px;'>{card['delta']}</div>"
                        f"<div style='color:#B9C7D8;line-height:1.55;font-size:0.90rem;'>{card['note']}</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


def render_advisor_summary(
    result: dict,
    readiness_df: pd.DataFrame,
    suggestions: "list[SuggestionItem] | None" = None,
    calculation_inputs: dict | None = None,
) -> None:
    sections = build_advisor_summary_sections(result, readiness_df, suggestions)
    border = "rgba(255,255,255,0.08)"
    body_color = "#D9E3F0"
    label_color = "#8FA8C6"
    muted_body_color = "#B9C7D8"
    section_styles = {
        "Claim Opportunities": {
            "card_bg": "linear-gradient(180deg, #132338 0%, #0F1A29 100%)",
            "border_color": "rgba(94, 166, 255, 0.32)",
            "label_color": "#BFD9FF",
            "badge_bg": "rgba(94, 166, 255, 0.16)",
            "badge_text": "Priority Review",
            "body_color": "#F2F7FF",
            "min_height": "276px",
        },
        "Review-Only Items": {
            "card_bg": "#0F1724",
            "border_color": "rgba(255,255,255,0.06)",
            "label_color": "#7F97B2",
            "badge_bg": "rgba(143, 168, 198, 0.12)",
            "badge_text": "File Review",
            "body_color": muted_body_color,
            "min_height": "252px",
        },
        "Verification": {
            "card_bg": "#111B28",
            "border_color": "rgba(196, 214, 235, 0.12)",
            "label_color": "#9EB4CC",
            "badge_bg": "rgba(158, 180, 204, 0.12)",
            "badge_text": "Support Check",
            "body_color": body_color,
            "min_height": "252px",
        },
    }

    with st.container(border=True):
        st.markdown("##### Advisor Summary")
        results_render_advisor_scenario_compare(
            result,
            calculation_inputs,
            calculate_personal_tax_return=calculate_personal_tax_return,
            format_currency=format_currency,
        )
        columns = st.columns([1.02, 1.04, 1.0], gap="medium")
        for index, (column, (title, items)) in enumerate(zip(columns, sections)):
            with column:
                style = section_styles.get(
                    title,
                    {
                        "card_bg": "#101826",
                        "border_color": border,
                        "label_color": label_color,
                        "badge_bg": "rgba(143, 168, 198, 0.12)",
                        "badge_text": "Memo Note",
                        "body_color": body_color,
                        "min_height": "250px",
                    },
                )
                if title == "Claim Opportunities" and items:
                    lead_item = items[0]
                    remaining_items = items[1:]
                    lead_summary = lead_item
                    lead_step = ""
                    if ". Check " in lead_item:
                        lead_summary, lead_step_suffix = lead_item.split(". Check ", 1)
                        lead_summary = lead_summary.strip() + "."
                        lead_step = f"Check {lead_step_suffix.strip()}"
                    next_step_html = (
                        f"<div style='color:{style['label_color']};line-height:1.45;font-size:0.90rem;'>Next step: {lead_step}</div>"
                        if lead_step
                        else ""
                    )
                    lead_html = (
                        "<div style='margin:2px 0 14px 0;padding:12px 13px 12px 13px;"
                        "border-radius:12px;background:rgba(94, 166, 255, 0.12);"
                        "border:1px solid rgba(94, 166, 255, 0.22);'>"
                        "<div style='font-size:0.70rem;letter-spacing:0.06em;text-transform:uppercase;"
                        f"color:{style['label_color']};font-weight:700;margin-bottom:6px;'>Primary Opportunity</div>"
                        f"<div style='color:{style['body_color']};line-height:1.5;font-weight:600;margin-bottom:{'7px' if lead_step else '0'};'>{lead_summary}</div>"
                        f"{next_step_html}"
                        "</div>"
                    )
                    bullet_html = "".join(
                        f"<li style='margin:0 0 10px 0;'>{entry}</li>"
                        for entry in remaining_items
                    )
                else:
                    lead_html = ""
                    bullet_html = "".join(
                        f"<li style='margin:0 0 10px 0;'>{entry}</li>"
                        for entry in items
                    )
                st.markdown(
                    (
                        f"<div style='background:{style['card_bg']};border:1px solid {style['border_color']};border-radius:16px;"
                        f"padding:15px 17px 16px 17px;min-height:{style['min_height']};"
                        f"margin:{'0 8px 6px 0' if index == 0 else '0 6px 6px 6px' if index == 1 else '0 0 6px 8px'};'>"
                        f"<div style='display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:10px;'>"
                        f"<div style='font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;color:{style['label_color']};font-weight:700;'>{title}</div>"
                        f"<span style='display:inline-block;padding:4px 10px;border-radius:999px;background:{style['badge_bg']};color:{style['label_color']};font-size:0.72rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;'>{style['badge_text']}</span>"
                        f"</div>"
                        f"{lead_html}"
                        f"<ul style='margin:0;padding-left:18px;color:{style['body_color']};line-height:1.62;'>{bullet_html}</ul>"
                        f"</div>"
                    ),
                    unsafe_allow_html=True,
                )
def render_answer_summary_sheet(
    result: dict,
    province_name: str,
    readiness_df: pd.DataFrame,
    suggestions: "list[SuggestionItem] | None" = None,
    calculation_inputs: dict | None = None,
) -> None:
    ready_count = int((readiness_df["Status"] == "Ready").sum()) if not readiness_df.empty else 0
    review_count = int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0
    missing_count = int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0
    return_memo_text = results_build_return_memo_html(result, format_currency=format_currency)
    memo_shell_bg = "#0D1522"
    memo_border = "rgba(255,255,255,0.08)"
    memo_label_color = "#8FA8C6"
    memo_body_color = "#D9E3F0"

    st.markdown(
        (
            f"<div style='background:{memo_shell_bg};border:1px solid {memo_border};border-radius:18px;"
            f"padding:16px 20px;margin:2px 0 14px 0;'>"
            f"<div style='font-size:0.78rem;letter-spacing:0.08em;text-transform:uppercase;color:{memo_label_color};font-weight:700;margin-bottom:8px;'>Return Memo</div>"
            f"<div style='color:{memo_body_color};line-height:1.65;font-size:0.95rem;'>{return_memo_text}</div>"
            f"</div>"
        ),
        unsafe_allow_html=True,
    )

    render_metric_row(
        [
            ("Total Income", result.get("total_income", 0.0)),
            ("Taxable Income", result.get("taxable_income", 0.0)),
            ("Total Payable", result.get("total_payable", 0.0)),
            ("Tax Withheld", result.get("income_tax_withheld", 0.0)),
        ],
        4,
    )
    st.caption(f"Filing snapshot: Ready {ready_count}, Review {review_count}, Missing {missing_count}.")
    if suggestions:
        results_render_tax_optimization_panel(result, suggestions, format_currency=format_currency)
    results_render_advisor_scenario_compare(
        result,
        calculation_inputs,
        calculate_personal_tax_return=calculate_personal_tax_return,
        format_currency=format_currency,
    )


def render_flow_stepper(current_step: int) -> None:
    with st.container(border=True):
        st.markdown("#### Guided Flow")
        step_tokens = []
        for step_number, step_label in FLOW_STEPS:
            if step_number < current_step:
                token = f"`● {step_number}. {step_label}`"
            elif step_number == current_step:
                token = f"**● {step_number}. {step_label}**"
            else:
                token = f"`○ {step_number}. {step_label}`"
            step_tokens.append(token)
        st.markdown("  ".join(step_tokens))
        st.caption("Work from left to right. Use the Next buttons to move through the return in order.")


def build_currency_df(rows: list[dict], currency_columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for column in currency_columns:
        if column in df.columns:
            df[column] = df[column].map(format_currency)
    return df


def build_label_amount_df(rows: list[tuple[str, float]], label_key: str = "Item", amount_key: str = "Amount") -> pd.DataFrame:
    return build_currency_df(
        [{label_key: label, amount_key: value} for label, value in rows],
        [amount_key],
    )


def read_public_markdown_doc(filename: str) -> str:
    path = Path(__file__).resolve().parent / filename
    if not path.exists():
        return f"_The file `{filename}` is not available in the current workspace._"
    return path.read_text(encoding="utf-8")


def build_report_pack_snapshot_lists(
    readiness_df: pd.DataFrame,
    assumptions_df: pd.DataFrame,
    missing_support_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame | None,
) -> tuple[list[str], list[str], list[str]]:
    ready_count = int((readiness_df["Status"] == "Ready").sum()) if not readiness_df.empty else 0
    review_count = int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0
    missing_count = int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0

    quick_review_items = [
        f"Readiness counts: Ready {ready_count}, Review {review_count}, Missing {missing_count}",
    ]
    if not readiness_df.empty:
        for _, row in readiness_df[readiness_df["Status"] != "Ready"].head(3).iterrows():
            quick_review_items.append(f'{row["Status"]}: {row["Area"]} - {row["Checklist Item"]}')

    top_override_items: list[str] = []
    if not assumptions_df.empty:
        flagged_overrides = assumptions_df[
            assumptions_df["Treatment"].astype(str).str.contains("Manual Override|Cap Applied", case=False, regex=True)
        ]
        for _, row in flagged_overrides.head(4).iterrows():
            item = f'{row["Area"]}: {row["Item"]} ({row["Treatment"]})'
            top_override_items.append(item)
            if len(quick_review_items) < 7:
                quick_review_items.append(f'{row["Treatment"]}: {row["Area"]} - {row["Item"]}')

    if reconciliation_df is not None and not reconciliation_df.empty:
        flagged_reconciliation = reconciliation_df[reconciliation_df["Status"].astype(str) == "Review difference"]
        for _, row in flagged_reconciliation.head(2).iterrows():
            quick_review_items.append(
                f'Reconciliation review: {row["Area"]} difference {row["Difference"]}'
            )

    top_warning_items: list[str] = []
    if not readiness_df.empty:
        for _, row in readiness_df[readiness_df["Status"].astype(str) != "Ready"].head(2).iterrows():
            top_warning_items.append(f'{row["Area"]}: {row["Checklist Item"]}')
    if not missing_support_df.empty:
        for _, row in missing_support_df.head(2).iterrows():
            top_warning_items.append(f'{row["Area"]}: {row["Suggested Support"]}')

    return quick_review_items, top_warning_items, top_override_items


def build_reconciliation_card_html(row: pd.Series, style: dict[str, str]) -> str:
    return f"""
    <div style="border:1px solid #2a2f3a;border-radius:12px;padding:12px 14px;margin:8px 0;background:#111827;">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px;">
            <span style="background:{style['bg']};color:{style['fg']};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{row['Status']}</span>
            <span style="color:#9ca3af;font-size:0.8rem;font-weight:600;">{row['Group']}</span>
            <span style="color:#f9fafb;font-weight:600;">{row['Area']}</span>
        </div>
        <div style="color:#d1d5db;line-height:1.5;">
            Slip total: {row['Slip Total']}<br>
            Manual / extra input: {row['Manual / Extra Input']}<br>
            Return amount used: {row['Return Amount Used']}<br>
            Difference: {row['Difference']}<br>
            Why it differs: {row.get('Explanation', 'No extra explanation recorded.')}
        </div>
    </div>
    """


def render_breakdown_lines(items: list[tuple[str, float]]) -> None:
    for label, value in items:
        st.write(f"{label}: {format_currency(value)}")

def render_assumptions_overrides_panel(df: pd.DataFrame) -> None:
    if df.empty:
        st.caption("No notable assumptions, overrides, or cap-driven adjustments were detected.")
        return

    def classify_treatment(treatment: str) -> tuple[str, dict[str, str]]:
        normalized = treatment.lower()
        if "manual override" in normalized:
            return "Manual Override", {"bg": "#7f1d1d", "fg": "#fecaca"}
        if "auto" in normalized:
            return "Auto Estimate", {"bg": "#1e3a8a", "fg": "#bfdbfe"}
        if "capped" in normalized:
            return "Cap Applied", {"bg": "#78350f", "fg": "#fde68a"}
        if "calculated" in normalized or "return value" in normalized or "default" in normalized:
            return "Calculated", {"bg": "#14532d", "fg": "#bbf7d0"}
        return "Info", {"bg": "#374151", "fg": "#f3f4f6"}

    manual_count = 0
    auto_count = 0
    capped_count = 0
    calculated_count = 0
    for _, row in df.iterrows():
        badge, _ = classify_treatment(str(row["Treatment"]))
        if badge == "Manual Override":
            manual_count += 1
        elif badge == "Auto Estimate":
            auto_count += 1
        elif badge == "Cap Applied":
            capped_count += 1
        elif badge == "Calculated":
            calculated_count += 1

    render_metric_row(
        [
            ("Manual Overrides", float(manual_count)),
            ("Auto Estimates", float(auto_count)),
            ("Caps Applied", float(capped_count)),
            ("Calculated Paths", float(calculated_count)),
        ],
        4,
        formatter=format_plain_number,
    )

    for _, row in df.iterrows():
        badge_label, style = classify_treatment(str(row["Treatment"]))
        st.markdown(
            f"""
            <div style="border:1px solid #2a2f3a;border-radius:12px;padding:12px 14px;margin:8px 0;background:#111827;">
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px;">
                    <span style="background:{style['bg']};color:{style['fg']};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{badge_label}</span>
                    <span style="color:#d1d5db;font-size:0.85rem;font-weight:600;">{row['Area']}</span>
                    <span style="color:#f9fafb;font-weight:600;">{row['Item']}</span>
                </div>
                <div style="color:#d1d5db;line-height:1.5;">
                    <strong style="color:#f3f4f6;">{row['Treatment']}</strong><br>
                    {row['Detail']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_reconciliation_panel(df: pd.DataFrame) -> None:
    if df.empty:
        st.caption("No reconciliation rows are available yet.")
        return

    status_styles = {
        "Matched": {"bg": "#14532d", "fg": "#bbf7d0"},
        "Matched with manual input": {"bg": "#1e3a8a", "fg": "#bfdbfe"},
        "Review difference": {"bg": "#78350f", "fg": "#fde68a"},
    }
    render_metric_row(
        [
            ("Matched", float((df["Status"] == "Matched").sum())),
            ("Matched + Manual", float((df["Status"] == "Matched with manual input").sum())),
            ("Review", float((df["Status"] == "Review difference").sum())),
        ],
        3,
        formatter=lambda value: str(int(value)),
    )
    selected_groups = st.multiselect(
        "Reconciliation groups",
        options=list(df["Group"].dropna().unique()),
        default=list(df["Group"].dropna().unique()),
        key="reconciliation_groups_filter",
    )
    only_review = st.checkbox(
        "Only show review differences",
        value=False,
        key="reconciliation_only_review_filter",
    )
    filtered_df = df[df["Group"].isin(selected_groups)] if selected_groups else df.copy()
    if only_review:
        filtered_df = filtered_df[filtered_df["Status"] == "Review difference"]
    if filtered_df.empty:
        st.caption("No reconciliation rows match the current filters.")
        return
    for group_name, group_df in filtered_df.groupby("Group", sort=False):
        st.markdown(f"##### {group_name}")
        for _, row in group_df.iterrows():
            style = status_styles.get(str(row["Status"]), {"bg": "#374151", "fg": "#f3f4f6"})
            st.markdown(build_reconciliation_card_html(row, style), unsafe_allow_html=True)


def render_filing_readiness_panel(df: pd.DataFrame) -> None:
    if df.empty:
        st.caption("No filing-readiness rows are available yet.")
        return

    status_styles = {
        "Ready": {"bg": "#14532d", "fg": "#bbf7d0"},
        "Review": {"bg": "#78350f", "fg": "#fde68a"},
        "Missing": {"bg": "#7f1d1d", "fg": "#fecaca"},
    }
    render_metric_row(
        [
            ("Ready", float((df["Status"] == "Ready").sum())),
            ("Review", float((df["Status"] == "Review").sum())),
            ("Missing", float((df["Status"] == "Missing").sum())),
        ],
        3,
        formatter=lambda value: str(int(value)),
    )
    for _, row in df.iterrows():
        style = status_styles.get(str(row["Status"]), {"bg": "#374151", "fg": "#f3f4f6"})
        st.markdown(
            f"""
            <div style="border:1px solid #2a2f3a;border-radius:12px;padding:12px 14px;margin:8px 0;background:#111827;">
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px;">
                    <span style="background:{style['bg']};color:{style['fg']};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{row['Status']}</span>
                    <span style="color:#d1d5db;font-size:0.85rem;font-weight:600;">{row['Area']}</span>
                    <span style="color:#f9fafb;font-weight:600;">{row['Checklist Item']}</span>
                </div>
                <div style="color:#d1d5db;line-height:1.5;">{row['Detail']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_advanced_technical_details(
    result: dict,
    province: str,
    province_name: str,
    tax_year: int,
    t4_reference_box24_total: float,
    t4_reference_box26_total: float,
    t4_reference_box52_total: float,
) -> None:
    st.divider()
    with st.expander("Advanced Technical Details", expanded=False):
        with st.expander("Federal Breakdown", expanded=False):
            render_breakdown_lines(
                [
                    ("Federal Basic Tax", result["federal_basic_tax"]),
                    ("Federal Dividend Tax Credit", result["federal_dividend_tax_credit"]),
                    ("Taxable Eligible Dividends Used", result["taxable_eligible_dividends"]),
                    ("Taxable Non-Eligible Dividends Used", result["taxable_non_eligible_dividends"]),
                    ("Federal Age Amount Used", result["federal_age_amount_auto"]),
                    ("Federal Medical Claim Used", result["federal_medical_claim"]),
                    ("Auto Spouse Amount Used", result["auto_spouse_amount"]),
                    ("Auto Eligible Dependant Amount Used", result["auto_eligible_dependant_amount"]),
                    ("Federal Foreign Tax Credit", result["federal_foreign_tax_credit"]),
                    ("Federal Foreign Tax Credit Limit", result["federal_foreign_tax_credit_limit"]),
                    ("T2209 Basic Federal Tax Used", result["t2209_basic_federal_tax_used"]),
                    ("T2209 Foreign Income Ratio", result["t2209_foreign_income_ratio"]),
                    ("T2209 Proportional Limit Before 15% Cap", result["t2209_limit_before_property_cap"]),
                    ("Foreign Property 15% Limit", result["foreign_property_limit"]),
                    ("T2209 Line 1 Tax Paid Used", result["t2209_non_business_tax_paid"]),
                    ("T2209 Line 2 Net Foreign Income Used", result["t2209_net_foreign_non_business_income"]),
                    ("T2209 Net Income Used", result["t2209_net_income"]),
                    ("Schedule 9 First $200", result["donation_first_200"]),
                    ("Schedule 9 Amount Above $200", result["donation_amount_above_200"]),
                    ("Schedule 9 High-Rate Portion", result["donation_high_rate_portion"]),
                    ("Schedule 9 Carryforward Used", result.get("schedule9_carryforward_claim_used", 0.0)),
                    ("Schedule 9 Carryforward Unused", result.get("schedule9_carryforward_unused", 0.0)),
                    ("Federal Donation Credit", result["federal_donation_credit"]),
                    ("Schedule 11 Current-Year Tuition Available", result["schedule11_current_year_tuition_available"]),
                    ("Schedule 11 Carryforward Available", result["schedule11_carryforward_available"]),
                    ("Schedule 11 Tuition Claimed", result["schedule11_total_claim_used"]),
                    ("Schedule 11 Unused Tuition Remaining", result["schedule11_total_unused"]),
                    ("Tuition Transfer From Spouse", result["schedule11_transfer_from_spouse"]),
                    ("Federal Credits", result["federal_non_refundable_credits"]),
                    ("Federal Net Tax", result["federal_tax"]),
                ]
            )

        with st.expander("Refundable Credits Breakdown", expanded=False):
            refundable_rows = build_currency_df(
                [
                    {"Component": "Canada Workers Benefit", "Amount": result.get("canada_workers_benefit", 0.0)},
                    {"Component": "CWB Auto Estimate", "Amount": result.get("canada_workers_benefit_auto", 0.0)},
                    {"Component": "CWB Disability Supplement Auto", "Amount": result.get("cwb_disability_supplement_auto", 0.0)},
                    {"Component": "CWB Disability Supplement Phaseout", "Amount": result.get("cwb_disability_supplement_phaseout", 0.0)},
                    {"Component": "CWB Manual Override", "Amount": result.get("canada_workers_benefit_manual", 0.0)},
                    {"Component": "CWB Phaseout", "Amount": result.get("canada_workers_benefit_phaseout", 0.0)},
                    {"Component": "Canada Training Credit", "Amount": result.get("canada_training_credit", 0.0)},
                    {"Component": "Training Credit Auto Estimate", "Amount": result.get("canada_training_credit_auto", 0.0)},
                    {"Component": "Training Credit Manual Override", "Amount": result.get("canada_training_credit_manual", 0.0)},
                    {"Component": "Training Credit Limit Available", "Amount": result.get("canada_training_credit_limit_available", 0.0)},
                    {"Component": "Medical Expense Supplement", "Amount": result.get("medical_expense_supplement", 0.0)},
                    {"Component": "Medical Supplement Auto Estimate", "Amount": result.get("medical_expense_supplement_auto", 0.0)},
                    {"Component": "Medical Supplement Manual Override", "Amount": result.get("medical_expense_supplement_manual", 0.0)},
                    {"Component": "Medical Supplement Phaseout", "Amount": result.get("medical_expense_supplement_phaseout", 0.0)},
                    {"Component": "CPP Overpayment Refund Estimate", "Amount": result.get("cpp_overpayment_refund", 0.0)},
                    {"Component": "EI Overpayment Refund Estimate", "Amount": result.get("ei_overpayment_refund", 0.0)},
                    {"Component": "CPP/EI Overpayment Refund Total", "Amount": result.get("payroll_overpayment_refund_total", 0.0)},
                    {"Component": "Other Federal Refundable Credits", "Amount": result.get("other_federal_refundable_credits", 0.0)},
                    {"Component": f"Other {province_name} Refundable Credits", "Amount": result.get("manual_provincial_refundable_credits", 0.0)},
                    {"Component": "Ontario Fertility Credit", "Amount": result.get("ontario_fertility_credit", 0.0)},
                    {"Component": "Ontario Seniors' Transit Credit", "Amount": result.get("ontario_seniors_transit_credit", 0.0)},
                    {"Component": "B.C. Renter's Credit", "Amount": result.get("bc_renters_credit", 0.0)},
                    {"Component": "B.C. Home Renovation Credit", "Amount": result.get("bc_home_renovation_credit", 0.0)},
                    {"Component": "Saskatchewan Fertility Credit", "Amount": result.get("sk_fertility_credit", 0.0)},
                    {"Component": "P.E.I. Volunteer Credit", "Amount": result.get("pe_volunteer_credit", 0.0)},
                    {"Component": "Other Manual Refundable Credits", "Amount": result.get("other_manual_refundable_credits", 0.0)},
                    {"Component": "Federal Refundable Credits Subtotal", "Amount": result.get("federal_refundable_credits", 0.0)},
                    {"Component": "Manual Refundable Credits Total", "Amount": result.get("manual_refundable_credits_total", 0.0)},
                    {"Component": "Province Special Refundable Credits", "Amount": result.get("provincial_special_refundable_credits", 0.0)},
                    {"Component": "Total Refundable Credits Used", "Amount": result.get("refundable_credits", 0.0)},
                ],
                ["Amount"],
            )
            st.dataframe(refundable_rows, use_container_width=True, hide_index=True)

        with st.expander(f"{province_name} Breakdown", expanded=False):
            render_breakdown_lines(
                [
                    (f"{province_name} Basic Tax", result["provincial_basic_tax"]),
                    (f"{province_name} Non-Refundable Credits", result["provincial_non_refundable_credits"]),
                    (f"{province_name} Age Amount Used", result.get("provincial_age_amount_auto", 0.0)),
                    (f"{province_name} Pension Amount Used", result.get("provincial_pension_amount", 0.0)),
                    (f"{province_name} Caregiver Claim Base Used", result.get("provincial_caregiver_claim_amount", 0.0)),
                    (f"{province_name} Medical Claim Used", result.get("provincial_medical_claim", 0.0)),
                    (f"{province_name} Donation Credit", result.get("provincial_donation_credit", 0.0)),
                    (f"{province_name} Dividend Tax Credit Auto", result.get("provincial_dividend_tax_credit_auto", 0.0)),
                    (f"{province_name} Dividend Tax Credit", result.get("provincial_dividend_tax_credit", 0.0)),
                    (f"{province_name} Low-Income Reduction", result.get("provincial_low_income_reduction", 0.0)),
                    (f"{province_name} Tax Reduction", result.get("provincial_tax_reduction", 0.0)),
                ]
            )
            if province in {"ON", "BC", "AB"}:
                provincial_household_rows = build_currency_df(
                    [
                        {"Household Line": "Spouse", "Requested/Manual": result.get("provincial_spouse_claim_manual_component", 0.0), "Auto": result.get("provincial_spouse_claim_auto_component", 0.0), "Used": result.get("provincial_spouse_claim", 0.0)},
                        {"Household Line": "Eligible dependant", "Requested/Manual": result.get("provincial_eligible_claim_manual_component", 0.0), "Auto": result.get("provincial_eligible_claim_auto_component", 0.0), "Used": result.get("provincial_eligible_dependant_claim", 0.0)},
                        {"Household Line": "Caregiver", "Requested/Manual": result.get("provincial_caregiver_requested_component", 0.0), "Auto": result.get("provincial_caregiver_available_component", 0.0), "Used": result.get("provincial_caregiver_claim", 0.0)},
                        {"Household Line": "Disability transfer", "Requested/Manual": result.get("requested_disability_transfer", 0.0), "Auto": result.get("available_disability_transfer", 0.0), "Used": result.get("provincial_disability_transfer_component", 0.0)},
                    ],
                    ["Requested/Manual", "Auto", "Used"],
                )
                st.markdown(f"#### {province_name} Household Line Detail")
                st.dataframe(provincial_household_rows, use_container_width=True, hide_index=True)
                st.caption(
                    f"Spouse: {result.get('provincial_spouse_household_reason', '')} "
                    f"Eligible dependant: {result.get('provincial_eligible_household_reason', '')} "
                    f"Caregiver target: {result.get('caregiver_claim_target', 'Auto')} ({result.get('provincial_caregiver_household_reason', '')}) "
                    f"Disability source: {result.get('disability_transfer_source', 'Auto')} ({result.get('provincial_disability_household_reason', '')})"
                )
            if province == "ON":
                render_breakdown_lines(
                    [
                        ("Ontario Age Amount Used", result["ontario_age_amount_auto"]),
                        ("Ontario Pension Amount Used", result["ontario_pension_amount"]),
                        ("Ontario Medical Claim Used", result["ontario_medical_claim"]),
                        ("Ontario Medical Other Dependants Claim", result["ontario_medical_dependant_claim"]),
                        ("Ontario Child Tax Reduction", result["ontario_child_reduction"]),
                        ("Ontario Impairment Reduction", result["ontario_impairment_reduction"]),
                        ("Ontario Dividend Tax Credit Auto", result["ontario_dividend_tax_credit_auto"]),
                        ("Ontario Dividend Tax Credit", result["ontario_dividend_tax_credit"]),
                        ("Ontario Foreign Tax Credit", result["provincial_foreign_tax_credit"]),
                        ("T2036 Line 1 Residual Foreign Tax", result["t2036_line1"]),
                        ("T2036 Provincial Tax Otherwise Payable", result["provincial_tax_otherwise_payable"]),
                        ("T2036 Foreign Income Ratio", result["t2036_foreign_income_ratio"]),
                        ("T2036 Limit", result["t2036_limit"]),
                        ("T2036 Residual Foreign Tax Unclaimed", result["t2036_unused_foreign_tax"]),
                        ("Ontario Donation Credit", result["ontario_donation_credit"]),
                        ("Ontario LIFT Max Credit", result["lift_max_credit"]),
                        ("Ontario LIFT Reduction Base", result["lift_reduction_base"]),
                        ("Ontario LIFT Credit", result["lift_credit"]),
                    ]
                )
            if province == "BC":
                render_breakdown_lines(
                    [
                        ("B.C. Tax Reduction Maximum", result.get("provincial_tax_reduction_max", 0.0)),
                        ("B.C. Tax Reduction Base", result.get("provincial_tax_reduction_base", 0.0)),
                    ]
                )
            if province == "AB":
                render_breakdown_lines([("Alberta Supplemental Tax Credit", result.get("ab_supplemental_tax_credit", 0.0))])
            if province == "MB":
                render_breakdown_lines([("MB479 Total Refundable Credits Used", result.get("provincial_special_refundable_credits", 0.0))])
            if province == "NS":
                render_breakdown_lines(
                    [
                        ("NS479 Volunteer Credit", result.get("ns479_volunteer_credit", 0.0)),
                        ("NS479 Sports and Arts Credit", result.get("ns479_childrens_sports_arts_credit", 0.0)),
                    ]
                )
            if province == "NB":
                render_breakdown_lines(
                    [
                        ("NB Special Non-Refundable Credits", result.get("nb_special_non_refundable_credits", 0.0)),
                        ("NB Seniors' Home Renovation Credit", result.get("nb_seniors_home_renovation_credit", 0.0)),
                    ]
                )
            if province == "NL":
                render_breakdown_lines(
                    [
                        ("NL Special Non-Refundable Credits", result.get("nl_special_non_refundable_credits", 0.0)),
                        ("NL479 Refundable Credits", result.get("nl479_other_refundable_credits", 0.0)),
                    ]
                )
            render_breakdown_lines(
                [
                    (f"{province_name} Surtax", result["provincial_surtax"]),
                    (f"{province_name} Health Premium", result["provincial_health_premium"]),
                    (f"{province_name} Net Tax", result["provincial_tax"]),
                ]
            )

        with st.expander("CPP / EI Breakdown", expanded=False):
            render_breakdown_lines(
                [
                    ("Employee CPP", result["employee_cpp"]),
                    ("CPP Deduction Included in Return", result["cpp_deduction"]),
                    ("CPP Amount Used for Credits", result["cpp_credit_base"]),
                    ("EI", result["ei"]),
                ]
            )

        with st.expander("T4 Reference Boxes", expanded=False):
            t4_params = TAX_CONFIGS[tax_year]
            estimator_ei_insurable_earnings = min(result.get("line_10100", 0.0), t4_params["ei_max_insurable_earnings"])
            estimator_cpp_pensionable_earnings = max(
                0.0,
                min(result.get("line_10100", 0.0), t4_params["cpp_ympe"]) - t4_params["cpp_basic_exemption"],
            )
            t4_reference_rows = build_currency_df(
                [
                    {"Reference": "T4 Box 24 EI Insurable Earnings", "Slip Total": t4_reference_box24_total, "Estimator Base": estimator_ei_insurable_earnings},
                    {"Reference": "T4 Box 26 CPP Pensionable Earnings", "Slip Total": t4_reference_box26_total, "Estimator Base": estimator_cpp_pensionable_earnings},
                    {"Reference": "T4 Box 52 Pension Adjustment", "Slip Total": t4_reference_box52_total, "Estimator Base": 0.0},
                ],
                ["Slip Total", "Estimator Base"],
            )
            st.dataframe(t4_reference_rows, use_container_width=True, hide_index=True)
            st.caption(
                "Box 24 and Box 26 are compared against the estimator's EI and CPP base assumptions. Box 52 is shown as a reference amount only and does not currently change the tax estimate directly."
            )

        with st.expander("Tax Formula Notes", expanded=False):
            st.markdown(
                """
                - `Total income` includes employment, pension, interest, dividend gross-up, taxable capital gains, net rental income, and other taxable income.
                - `Net income` subtracts deductions such as RRSP, FHSA, RPP, dues, moving expenses, child care, carrying charges, support payments, and CPP deductions.
                - `Taxable income` equals net income after any loss carryforwards and other carryforward-style deductions used in the return.
                - Federal and provincial tax are calculated separately using progressive brackets and available credits.
                - For 2025, federal advanced credits are automated, and Ontario plus British Columbia now have richer province-specific credit logic.
                - Provincial dividend tax credits are auto-calculated for Ontario and British Columbia, with a manual override available for worksheet differences.
                - Foreign tax credit now uses a clearer worksheet path: source foreign income and tax, T2209 federal ratio limit, 15% foreign property cap, T2036 residual provincial credit, and any remaining unclaimed foreign tax.
                - Tuition now follows a clearer Schedule 11-style flow with current-year T2202 amounts, carryforward availability, claimed amounts, transfer-in amounts, and unused balances shown separately.
                - Donations now follow a closer Schedule 9 flow, including the high-rate federal portion above the 2025 taxable-income threshold.
                - British Columbia tax reduction and B.C. donation logic are now estimated from province-specific rules for 2025.
                - Manitoba MB428-A and MB479, Nova Scotia NS479, New Brunswick NB(S12), Newfoundland and Labrador NL special credits, and Prince Edward Island low-income worksheet views are now surfaced through province-specific schedule sections.
                - Alberta supplemental tax credit is estimated from the eligible provincial claim-base amounts currently modelled in the app. This is an inference from the AB428 guidance rather than a full worksheet clone.
                - Ontario LIFT credit is estimated using Schedule ON428-A style thresholds for 2025.
                - Eligible dependant auto-claims now respect the key restrictions you enter: spouse status, separation, living arrangement, support payments, and household exclusivity.
                - Refund or balance owing = income tax withheld + instalments + refundable credits + other payments - total income tax payable.
                """
            )


def empty_rows(columns: list[str], rows: int = 3) -> list[dict]:
    return [{column: 0.0 for column in columns} for _ in range(rows)]


def render_record_card_editor(
    title: str,
    card_key: str,
    fields: list[dict[str, object]],
    help_text: str | None = None,
    count_default: int = 1,
) -> pd.DataFrame:
    st.markdown(f"#### {title}")
    if help_text:
        st.caption(help_text)
    current_records = st.session_state.get(card_key)
    persisted_records = st.session_state.get(f"persist_{card_key}")
    source_records = current_records if isinstance(current_records, list) else persisted_records if isinstance(persisted_records, list) else []
    default_count = max(
        int(st.session_state.get(f"{card_key}_count", 0)),
        len(source_records),
        count_default,
    )
    count = int(
        st.number_input(
            f"Number of {title}",
            min_value=0,
            step=1,
            value=default_count,
            key=f"{card_key}_count",
        )
    )
    records: list[dict[str, float]] = []
    for index in range(count):
        with st.container(border=True):
            st.markdown(f"**{title} #{index + 1}**")
            cols = st.columns(2)
            record: dict[str, object] = {}
            for field_index, field in enumerate(fields):
                col = cols[field_index % 2]
                field_id = str(field["id"])
                field_type = str(field.get("type", "number"))
                widget_key = f"{card_key}_{index}_{field_id}"
                source_record = source_records[index] if index < len(source_records) else {}
                if field_type == "text":
                    record[field_id] = col.text_input(
                        str(field["label"]),
                        value=str(st.session_state.get(widget_key, source_record.get(field_id, field.get("value", "")))),
                        key=widget_key,
                        help=str(field.get("help", "")) if field.get("help") else None,
                        placeholder=str(field.get("placeholder", "")) if field.get("placeholder") else None,
                    )
                elif field_type == "select":
                    options = list(field.get("options", []))
                    default_value = st.session_state.get(widget_key, source_record.get(field_id, field.get("value", options[0] if options else "")))
                    default_index = options.index(default_value) if default_value in options else 0
                    record[field_id] = col.selectbox(
                        str(field["label"]),
                        options,
                        index=default_index,
                        key=widget_key,
                        help=str(field.get("help", "")) if field.get("help") else None,
                    )
                else:
                    record[field_id] = float(
                        col.number_input(
                            str(field["label"]),
                            min_value=0.0,
                            step=float(field.get("step", 100.0)),
                            value=float(st.session_state.get(widget_key, source_record.get(field_id, field.get("value", 0.0)))),
                            key=widget_key,
                            help=str(field.get("help", "")) if field.get("help") else None,
                        )
                    )
            records.append(record)
    st.session_state[card_key] = records
    st.session_state[f"persist_{card_key}"] = records
    return pd.DataFrame(records)


def render_t_slip_wizard_card(title: str, card_key: str, fields: list[dict[str, object]], count_default: int = 1) -> list[dict[str, float]]:
    st.markdown(f"#### {title}")
    microcopy = SLIP_WIZARD_MICROCOPY.get(card_key, {})
    if microcopy.get("should_fill"):
        st.caption(f"Should you fill this? {microcopy['should_fill']}")
    if microcopy.get("tip"):
        st.caption(f"Quick tip: {microcopy['tip']}")
    current_records = st.session_state.get(card_key)
    persisted_records = st.session_state.get(f"persist_{card_key}")
    source_records = current_records if isinstance(current_records, list) else persisted_records if isinstance(persisted_records, list) else []
    default_count = max(
        int(st.session_state.get(f"{card_key}_count", 0)),
        len(source_records),
        count_default,
    )
    count = int(
        st.number_input(
            f"Number of {title}",
            min_value=0,
            step=1,
            value=default_count,
            key=f"{card_key}_count",
        )
    )
    records: list[dict[str, float]] = []
    for index in range(count):
        with st.container(border=True):
            st.markdown(f"**{title} #{index + 1}**")
            columns = st.columns(2)
            record: dict[str, float] = {}
            for field_index, field in enumerate(fields):
                col = columns[field_index % 2]
                field_id = str(field["id"])
                widget_key = f"{card_key}_{index}_{field_id}"
                fallback_value = float((source_records[index] if index < len(source_records) else {}).get(field_id, 0.0))
                record[field_id] = float(
                    col.number_input(
                        str(field["label"]),
                        min_value=0.0,
                        step=float(field.get("step", 100.0)),
                        value=float(st.session_state.get(widget_key, fallback_value)),
                        key=widget_key,
                        help=str(field.get("help", "")) if field.get("help") else None,
                    )
                )
            records.append(record)
    st.session_state[card_key] = records
    return records


def render_slip_wizard_tabs(configs: list[dict[str, object]]) -> dict[str, list[dict[str, float]]]:
    records_by_key: dict[str, list[dict[str, float]]] = {}
    tabs = st.tabs([str(config["tab"]) for config in configs])
    for tab, config in zip(tabs, configs):
        with tab:
            records_by_key[str(config["key"])] = render_t_slip_wizard_card(
                str(config["title"]),
                str(config["key"]),
                list(config["fields"]),
            )
    return records_by_key


def read_slip_wizard_records_from_state(configs: list[dict[str, object]]) -> dict[str, list[dict[str, float]]]:
    records_by_key: dict[str, list[dict[str, float]]] = {}
    for config in configs:
        card_key = str(config["key"])
        fields = list(config["fields"])
        stored_records = st.session_state.get(card_key)
        persisted_records = st.session_state.get(f"persist_{card_key}")
        if isinstance(stored_records, list):
            normalized_records: list[dict[str, float]] = []
            count = max(int(st.session_state.get(f"{card_key}_count", 0)), len(stored_records))
            for index in range(count):
                stored_record = stored_records[index] if index < len(stored_records) else {}
                normalized_record: dict[str, float] = {}
                for field in fields:
                    field_id = str(field["id"])
                    widget_key = f"{card_key}_{index}_{field_id}"
                    if widget_key in st.session_state:
                        normalized_record[field_id] = float(st.session_state.get(widget_key, 0.0))
                    else:
                        normalized_record[field_id] = float((stored_record or {}).get(field_id, 0.0))
                normalized_records.append(normalized_record)
            records_by_key[card_key] = normalized_records
            continue
        if isinstance(persisted_records, list):
            normalized_records = []
            count = max(int(st.session_state.get(f"{card_key}_count", 0)), len(persisted_records))
            for index in range(count):
                stored_record = persisted_records[index] if index < len(persisted_records) else {}
                normalized_record: dict[str, float] = {}
                for field in fields:
                    field_id = str(field["id"])
                    widget_key = f"{card_key}_{index}_{field_id}"
                    if widget_key in st.session_state:
                        normalized_record[field_id] = float(st.session_state.get(widget_key, 0.0))
                    else:
                        normalized_record[field_id] = float((stored_record or {}).get(field_id, 0.0))
                normalized_records.append(normalized_record)
            records_by_key[card_key] = normalized_records
            continue
        count = int(st.session_state.get(f"{card_key}_count", 1))
        records: list[dict[str, float]] = []
        for index in range(count):
            record: dict[str, float] = {}
            for field in fields:
                field_id = str(field["id"])
                record[field_id] = float(st.session_state.get(f"{card_key}_{index}_{field_id}", 0.0))
            records.append(record)
        records_by_key[card_key] = records
    return records_by_key


def read_record_card_editor_state(
    card_key: str,
    fields: list[dict[str, object]],
    count_default: int = 1,
) -> pd.DataFrame:
    stored_records = st.session_state.get(card_key)
    persisted_records = st.session_state.get(f"persist_{card_key}")
    source_records = stored_records if isinstance(stored_records, list) else persisted_records
    if isinstance(source_records, list):
        normalized_records: list[dict[str, object]] = []
        for stored_record in source_records:
            normalized_record: dict[str, object] = {}
            for field in fields:
                field_id = str(field["id"])
                field_type = str(field.get("type", "number"))
                if field_type in {"text", "select"}:
                    normalized_record[field_id] = (stored_record or {}).get(field_id, field.get("value", ""))
                else:
                    normalized_record[field_id] = float((stored_record or {}).get(field_id, field.get("value", 0.0)))
            normalized_records.append(normalized_record)
        return pd.DataFrame(normalized_records)
    count = max(
        int(st.session_state.get(f"{card_key}_count", count_default)),
        len(source_records) if isinstance(source_records, list) else 0,
    )
    records: list[dict[str, object]] = []
    for index in range(count):
        record: dict[str, object] = {}
        for field in fields:
            field_id = str(field["id"])
            field_type = str(field.get("type", "number"))
            widget_key = f"{card_key}_{index}_{field_id}"
            if field_type in {"text", "select"}:
                record[field_id] = st.session_state.get(widget_key, field.get("value", ""))
            else:
                record[field_id] = float(st.session_state.get(widget_key, field.get("value", 0.0)))
        records.append(record)
    return pd.DataFrame(records)


def build_wizard_df(records: list[dict[str, float]], columns: list[str]) -> pd.DataFrame:
    return coerce_editor_df(pd.DataFrame(records or empty_rows(columns, 0)), columns)


def line_summary_df(result: dict, province_name: str) -> pd.DataFrame:
    rows = [
        {"Line": "10100", "Description": "Employment income", "Amount": result.get("line_10100", 0.0)},
        {"Line": "10400", "Description": "Other employment income", "Amount": result.get("line_10400", 0.0)},
        {"Line": "11500/11600", "Description": "Pension income", "Amount": result.get("line_pension_income", 0.0)},
        {"Line": "12800", "Description": "RRSP/RRIF income", "Amount": result.get("line_rrsp_rrif_income", 0.0)},
        {"Line": "12000", "Description": "Taxable eligible dividends", "Amount": result.get("taxable_eligible_dividends", 0.0)},
        {"Line": "12010", "Description": "Taxable non-eligible dividends", "Amount": result.get("taxable_non_eligible_dividends", 0.0)},
        {"Line": "12100", "Description": "Interest and investment income", "Amount": result.get("line_interest_income", 0.0)},
        {"Line": "12600", "Description": "Rental income", "Amount": result.get("line_rental_income", 0.0)},
        {"Line": "12700", "Description": "Taxable capital gains", "Amount": result.get("line_taxable_capital_gains", 0.0)},
        {"Line": "13000", "Description": "Other income", "Amount": result.get("line_other_income", 0.0)},
        {"Line": "15000", "Description": "Total income", "Amount": result.get("total_income", 0.0)},
        {"Line": "20800", "Description": "RRSP deduction", "Amount": result.get("line_rrsp_deduction", 0.0)},
        {"Line": "20805", "Description": "FHSA deduction", "Amount": result.get("line_fhsa_deduction", 0.0)},
        {"Line": "21400", "Description": "Carrying charges", "Amount": result.get("line_carrying_charges", 0.0)},
        {"Line": "21900", "Description": "Moving expenses", "Amount": result.get("line_moving_expenses", 0.0)},
        {"Line": "22000", "Description": "Support payments deduction", "Amount": result.get("line_support_payments_deduction", 0.0)},
        {"Line": "22100", "Description": "Child care expenses", "Amount": result.get("line_child_care_expenses", 0.0)},
        {"Line": "22215", "Description": "CPP enhanced contributions deduction", "Amount": result.get("line_22215", 0.0)},
        {"Line": "22200", "Description": "Dues", "Amount": result.get("line_union_dues", 0.0)},
        {"Line": "22900", "Description": "Other employment expenses", "Amount": result.get("line_other_employment_expenses", 0.0)},
        {"Line": "23600", "Description": "Net income", "Amount": result.get("net_income", 0.0)},
        {"Line": "25300", "Description": "Net capital loss carryforward", "Amount": result.get("net_capital_loss_carryforward", 0.0)},
        {"Line": "26000", "Description": "Taxable income", "Amount": result.get("taxable_income", 0.0)},
        {"Line": "30800", "Description": "CPP/QPP contributions on employment income", "Amount": result.get("line_30800", 0.0)},
        {"Line": "31200", "Description": "EI premiums on employment income", "Amount": result.get("line_31200", 0.0)},
        {"Line": "32300", "Description": "Tuition amount claimed", "Amount": result.get("schedule11_total_claim_used", 0.0)},
        {"Line": "34200", "Description": "Cultural / ecological gifts not subject to 75% limit", "Amount": result.get("schedule9_unlimited_gifts_claimed", 0.0)},
        {"Line": "34900", "Description": "Schedule 9 donation credit", "Amount": result.get("federal_donation_credit", 0.0)},
        {"Line": "40500", "Description": "Federal foreign tax credit", "Amount": result.get("federal_foreign_tax_credit", 0.0)},
        {"Line": "42800", "Description": f"{province_name} tax", "Amount": result.get("provincial_tax", 0.0)},
        {"Line": "43500", "Description": "Total payable", "Amount": result.get("total_payable", 0.0)},
        {"Line": "43700", "Description": "Total income tax deducted", "Amount": result.get("income_tax_withheld", 0.0)},
        {"Line": "44800", "Description": "CPP overpayment refund estimate", "Amount": result.get("cpp_overpayment_refund", 0.0)},
        {"Line": "45000", "Description": "EI overpayment refund estimate", "Amount": result.get("ei_overpayment_refund", 0.0)},
        {"Line": "45300", "Description": "Canada workers benefit incl. disability supplement", "Amount": result.get("canada_workers_benefit", 0.0)},
        {"Line": "47600", "Description": "Tax instalments paid", "Amount": result.get("installments_paid", 0.0)},
        {"Line": "48200", "Description": "Total credits and payments", "Amount": result.get("total_payments", 0.0)},
        {"Line": "48400", "Description": "Refund", "Amount": result.get("line_48400_refund", 0.0)},
        {"Line": "48500", "Description": "Balance owing", "Amount": result.get("line_48500_balance_owing", 0.0)},
    ]
    return pd.DataFrame(rows)


def coerce_editor_df(editor_df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in editor_df.columns:
            editor_df[column] = 0.0
        editor_df[column] = pd.to_numeric(editor_df[column], errors="coerce").fillna(0.0)
    return editor_df


st.set_page_config(page_title=META_TITLE, page_icon="📱", layout="wide")
inject_meta_tags()

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1080px;
        padding-top: 1.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div style="margin:0 0 -0.9rem 0;">
        <img src="data:image/png;base64,{base64.b64encode(Path(__file__).with_name("contexta_logo.png").read_bytes()).decode()}" alt="Contexta logo" style="width:144px;display:block;margin:0;" />
    </div>
    """,
    unsafe_allow_html=True,
)

st.title(
    "Advanced Canadian Personal Tax Estimator",
    help=(
        "Current scope: broad federal coverage across Canada, with deeper provincial handling for Ontario and British Columbia. "
        "Other provinces use core bracket and personal-credit rules plus any extra provincial amounts you enter."
    ),
)

with st.expander("Scope and assumptions", expanded=False):
    st.markdown(
        """
        - This estimator follows a T1-style flow: total income, deductions, taxable income, federal tax, provincial tax, and refund or balance owing.
        - Rental income can now be entered through T776-style property cards, with a manual additional net-rental fallback if needed.
        - Sole proprietorship and T2125 detail are intentionally excluded for now so we can focus on a stronger personal tax return experience.
        - Advanced credit automation in this round is strongest for 2025. If you are estimating 2026 and know a specific claim amount that differs, use the manual claim inputs to supplement the result.
        - For non-Ontario provinces, enter any extra provincial credits as dollar values in the provincial adjustments section.
        """
    )

if "current_flow_step" not in st.session_state:
    st.session_state["current_flow_step"] = 1

with st.container(border=True):
    st.markdown("#### Return Setup")
    setup_col1, setup_col2, setup_col3 = st.columns(3)
    tax_year = setup_col1.selectbox("Tax Year", AVAILABLE_TAX_YEARS, key="tax_year")
    province = setup_col2.selectbox(
        "Province",
        AVAILABLE_PROVINCES,
        index=AVAILABLE_PROVINCES.index("ON"),
        key="province",
        format_func=lambda code: PROVINCES[code],
    )
    age = int(
        setup_col3.number_input(
            "Age at Year End",
            min_value=0,
            max_value=120,
            value=int(st.session_state.get("age", 35)),
            key="age",
        )
    )
    with st.expander("Quick Start", expanded=False):
        st.markdown(
            """
            - `Only have T-slips?` Start with `1) Slips`. For many users, that may be enough.
            - `Have property sales or rental activity?` Review `2) Property and Capital Schedules`.
            - `Have income not already shown on slips?` Review `3) Income and Investment`.
            - `Have RRSP, FHSA, moving expenses, or other deductions?` Review `4) Deductions`.
            - `Have donations, medical expenses, spouse or dependant credits, tuition carryforwards, or foreign tax situations?` Review `5) Credits, Carryforwards, and Special Cases`.
            - `Made instalments or other tax payments outside your slips?` Review `6) Payments and Withholdings`.
            """
        )

province_name = PROVINCES[province]
current_step = int(st.session_state.get("current_flow_step", 1))

wizard_records = read_slip_wizard_records_from_state(SLIP_WIZARD_CONFIGS)
t4_wizard_records = wizard_records["t4_wizard"]
t4a_wizard_records = wizard_records["t4a_wizard"]
t5_wizard_records = wizard_records["t5_wizard"]
t3_wizard_records = wizard_records["t3_wizard"]
t4ps_wizard_records = wizard_records["t4ps_wizard"]
t2202_wizard_records = wizard_records["t2202_wizard"]

rental_schedule_fields = [
    {"id": "property_label", "type": "text"},
    {"id": "gross_rent"},
    {"id": "advertising"},
    {"id": "insurance"},
    {"id": "interest_bank_charges"},
    {"id": "property_taxes"},
    {"id": "utilities"},
    {"id": "repairs_maintenance"},
    {"id": "management_admin"},
    {"id": "travel"},
    {"id": "office_expenses"},
    {"id": "other_expenses"},
    {"id": "cca"},
]
capital_schedule_fields = [
    {"id": "description", "type": "text"},
    {"id": "proceeds"},
    {"id": "adjusted_cost_base"},
    {"id": "outlays_expenses"},
    {"id": "allowable_capital_loss_applied"},
]
additional_dependant_fields = [
    {"id": "dependant_label", "type": "text"},
    {"id": "category", "type": "select"},
    {"id": "infirm", "type": "select"},
    {"id": "lived_with_you", "type": "select"},
    {"id": "caregiver_claim_amount"},
    {"id": "disability_transfer_available_amount"},
    {"id": "medical_expenses_amount"},
    {"id": "medical_claim_shared", "type": "select"},
]
tuition_cf_fields = [
    {"id": "tax_year"},
    {"id": "available_amount"},
    {"id": "claim_amount"},
]
donation_cf_fields = tuition_cf_fields
provincial_credit_line_fields = [
    {"id": "line_code"},
    {"id": "amount"},
]

rental_schedule_df = read_record_card_editor_state("rental_schedules", rental_schedule_fields)
capital_schedule_df = read_record_card_editor_state("capital_gain_schedules", capital_schedule_fields)
additional_dependants_df = read_record_card_editor_state("additional_dependants", additional_dependant_fields, count_default=0)
tuition_cf_df = read_record_card_editor_state("tuition_carryforwards", tuition_cf_fields)
donation_cf_df = read_record_card_editor_state("donation_carryforwards", donation_cf_fields)
provincial_credit_lines_df = read_record_card_editor_state("provincial_credit_lines", provincial_credit_line_fields)

additional_dependant_count = len(additional_dependants_df.index)
additional_dependant_caregiver_claim_total = 0.0
additional_dependant_disability_transfer_available_total = 0.0
additional_dependant_medical_claim_total = 0.0
if not additional_dependants_df.empty:
    additional_dependants_work_df = additional_dependants_df.copy()
    if "category" not in additional_dependants_work_df.columns:
        additional_dependants_work_df["category"] = ""
    if "infirm" not in additional_dependants_work_df.columns:
        additional_dependants_work_df["infirm"] = "No"
    if "lived_with_you" not in additional_dependants_work_df.columns:
        additional_dependants_work_df["lived_with_you"] = "No"
    if "medical_claim_shared" not in additional_dependants_work_df.columns:
        additional_dependants_work_df["medical_claim_shared"] = "No"
    for numeric_col in [
        "caregiver_claim_amount",
        "disability_transfer_available_amount",
        "medical_expenses_amount",
    ]:
        if numeric_col not in additional_dependants_work_df.columns:
            additional_dependants_work_df[numeric_col] = 0.0
        additional_dependants_work_df[numeric_col] = pd.to_numeric(
            additional_dependants_work_df[numeric_col], errors="coerce"
        ).fillna(0.0)
    adult_categories = {"Adult child", "Parent/Grandparent", "Other adult relative"}
    additional_dependants_work_df["infirm_bool"] = additional_dependants_work_df["infirm"].eq("Yes")
    additional_dependants_work_df["lived_with_you_bool"] = additional_dependants_work_df["lived_with_you"].eq("Yes")
    additional_dependants_work_df["medical_claim_shared_bool"] = additional_dependants_work_df["medical_claim_shared"].eq("Yes")
    additional_dependant_caregiver_claim_total = float(
        additional_dependants_work_df.loc[
            additional_dependants_work_df["infirm_bool"]
            & additional_dependants_work_df["category"].isin(adult_categories),
            "caregiver_claim_amount",
        ].sum()
    )
    additional_dependant_disability_transfer_available_total = float(
        additional_dependants_work_df.loc[
            additional_dependants_work_df["infirm_bool"],
            "disability_transfer_available_amount",
        ].sum()
    )
    additional_dependant_medical_claim_total = float(
        additional_dependants_work_df.loc[
            additional_dependants_work_df["lived_with_you_bool"]
            & ~additional_dependants_work_df["medical_claim_shared_bool"],
            "medical_expenses_amount",
        ].sum()
    )

employment_income_manual = float(st.session_state.get("employment_income", 0.0))
pension_income_manual = float(st.session_state.get("pension_income", 0.0))
rrsp_rrif_income_manual = float(st.session_state.get("rrsp_rrif_income", 0.0))
other_income_manual = float(st.session_state.get("other_income", 0.0))
manual_net_rental_income = float(st.session_state.get("net_rental_income", 0.0))
manual_taxable_capital_gains = float(st.session_state.get("taxable_capital_gains", 0.0))
interest_income_manual = float(st.session_state.get("interest_income", 0.0))
eligible_dividends = float(st.session_state.get("eligible_dividends", 0.0))
non_eligible_dividends = float(st.session_state.get("non_eligible_dividends", 0.0))
t5_eligible_dividends_taxable = float(st.session_state.get("t5_eligible_dividends_taxable", 0.0))
t5_non_eligible_dividends_taxable = float(st.session_state.get("t5_non_eligible_dividends_taxable", 0.0))
t5_federal_dividend_credit = float(st.session_state.get("t5_federal_dividend_credit", 0.0))
t3_eligible_dividends_taxable = float(st.session_state.get("t3_eligible_dividends_taxable", 0.0))
t3_non_eligible_dividends_taxable = float(st.session_state.get("t3_non_eligible_dividends_taxable", 0.0))
t3_federal_dividend_credit = float(st.session_state.get("t3_federal_dividend_credit", 0.0))

rrsp_deduction = float(st.session_state.get("rrsp_deduction", 0.0))
fhsa_deduction = float(st.session_state.get("fhsa_deduction", 0.0))
rpp_contribution = float(st.session_state.get("rpp_contribution", 0.0))
union_dues = float(st.session_state.get("union_dues", 0.0))
child_care_expenses = float(st.session_state.get("child_care_expenses", 0.0))
moving_expenses = float(st.session_state.get("moving_expenses", 0.0))
support_payments_deduction = float(st.session_state.get("support_payments_deduction", 0.0))
carrying_charges = float(st.session_state.get("carrying_charges", 0.0))
other_employment_expenses = float(st.session_state.get("other_employment_expenses", 0.0))
other_deductions = float(st.session_state.get("other_deductions", 0.0))
net_capital_loss_carryforward = float(st.session_state.get("net_capital_loss_carryforward", 0.0))
other_loss_carryforward = float(st.session_state.get("other_loss_carryforward", 0.0))

spouse_claim_enabled = bool(st.session_state.get("spouse_claim_enabled", st.session_state.get("persist_spouse_claim_enabled", False)))
has_spouse_end_of_year = bool(st.session_state.get("has_spouse_end_of_year", st.session_state.get("persist_has_spouse_end_of_year", False)))
separated_in_year = bool(st.session_state.get("separated_in_year", st.session_state.get("persist_separated_in_year", False)))
support_payments_to_spouse = bool(st.session_state.get("support_payments_to_spouse", st.session_state.get("persist_support_payments_to_spouse", False)))
spouse_infirm = bool(st.session_state.get("spouse_infirm", st.session_state.get("persist_spouse_infirm", False)))
spouse_disability_transfer_available = bool(st.session_state.get("spouse_disability_transfer_available", st.session_state.get("persist_spouse_disability_transfer_available", False)))
spouse_disability_transfer_available_amount = float(st.session_state.get("spouse_disability_transfer_available_amount", st.session_state.get("persist_spouse_disability_transfer_available_amount", 0.0)))
spouse_net_income = float(st.session_state.get("spouse_net_income", st.session_state.get("persist_spouse_net_income", 0.0)))
eligible_dependant_claim_enabled = bool(st.session_state.get("eligible_dependant_claim_enabled", st.session_state.get("persist_eligible_dependant_claim_enabled", False)))
eligible_dependant_infirm = bool(st.session_state.get("eligible_dependant_infirm", st.session_state.get("persist_eligible_dependant_infirm", False)))
dependant_lived_with_you = bool(st.session_state.get("dependant_lived_with_you", st.session_state.get("persist_dependant_lived_with_you", False)))
eligible_dependant_net_income = float(st.session_state.get("eligible_dependant_net_income", st.session_state.get("persist_eligible_dependant_net_income", 0.0)))
dependant_relationship = str(st.session_state.get("dependant_relationship", st.session_state.get("persist_dependant_relationship", "Child")))
dependant_category = str(st.session_state.get("dependant_category", st.session_state.get("persist_dependant_category", "Minor child")))
dependant_disability_transfer_available = bool(st.session_state.get("dependant_disability_transfer_available", st.session_state.get("persist_dependant_disability_transfer_available", False)))
dependant_disability_transfer_available_amount = float(st.session_state.get("dependant_disability_transfer_available_amount", st.session_state.get("persist_dependant_disability_transfer_available_amount", 0.0)))
paid_child_support_for_dependant = bool(st.session_state.get("paid_child_support_for_dependant", st.session_state.get("persist_paid_child_support_for_dependant", False)))
shared_custody_claim_agreement = bool(st.session_state.get("shared_custody_claim_agreement", st.session_state.get("persist_shared_custody_claim_agreement", False)))
another_household_member_claims_dependant = bool(st.session_state.get("another_household_member_claims_dependant", st.session_state.get("persist_another_household_member_claims_dependant", False)))
another_household_member_claims_caregiver = bool(st.session_state.get("another_household_member_claims_caregiver", st.session_state.get("persist_another_household_member_claims_caregiver", False)))
another_household_member_claims_disability_transfer = bool(st.session_state.get("another_household_member_claims_disability_transfer", st.session_state.get("persist_another_household_member_claims_disability_transfer", False)))
medical_dependant_claim_shared = bool(st.session_state.get("medical_dependant_claim_shared", st.session_state.get("persist_medical_dependant_claim_shared", False)))
caregiver_claim_target = str(st.session_state.get("caregiver_claim_target", st.session_state.get("persist_caregiver_claim_target", "Auto")))
disability_transfer_source = str(st.session_state.get("disability_transfer_source", st.session_state.get("persist_disability_transfer_source", "Auto")))
spouse_amount_claim = float(st.session_state.get("spouse_amount_claim", st.session_state.get("persist_spouse_amount_claim", 0.0)))
eligible_dependant_claim = float(st.session_state.get("eligible_dependant_claim", st.session_state.get("persist_eligible_dependant_claim", 0.0)))
age_amount_claim = float(st.session_state.get("age_amount_claim", 0.0))
disability_amount_claim = float(st.session_state.get("disability_amount_claim", 0.0))
tuition_amount_claim = float(st.session_state.get("tuition_amount_claim", 0.0))
tuition_transfer_from_spouse = float(st.session_state.get("tuition_transfer_from_spouse", 0.0))
student_loan_interest = float(st.session_state.get("student_loan_interest", 0.0))
medical_expenses_paid = float(st.session_state.get("medical_expenses_paid", 0.0))
charitable_donations = float(st.session_state.get("charitable_donations", 0.0))
donations_eligible_total = float(st.session_state.get("donations_eligible_total", 0.0))
ecological_cultural_gifts = float(st.session_state.get("ecological_cultural_gifts", 0.0))
ecological_gifts_pre2016 = float(st.session_state.get("ecological_gifts_pre2016", 0.0))
additional_federal_credits = float(st.session_state.get("additional_federal_credits", 0.0))
additional_provincial_credit_amount = float(st.session_state.get("additional_provincial_credit_amount", 0.0))
ontario_caregiver_amount = float(st.session_state.get("ontario_caregiver_amount", 0.0))
ontario_student_loan_interest = float(st.session_state.get("ontario_student_loan_interest", 0.0))
ontario_tuition_transfer = float(st.session_state.get("ontario_tuition_transfer", 0.0))
ontario_disability_transfer = float(st.session_state.get("ontario_disability_transfer", 0.0))
ontario_adoption_expenses = float(st.session_state.get("ontario_adoption_expenses", 0.0))
ontario_medical_dependants = float(st.session_state.get("ontario_medical_dependants", 0.0))
ontario_dependent_children_count = float(st.session_state.get("ontario_dependent_children_count", 0.0))
ontario_dependant_impairment_count = float(st.session_state.get("ontario_dependant_impairment_count", 0.0))
foreign_income = float(st.session_state.get("foreign_income", 0.0))
foreign_tax_paid = float(st.session_state.get("foreign_tax_paid", 0.0))
ontario_dividend_tax_credit_manual = float(st.session_state.get("provincial_dividend_tax_credit_manual", 0.0))
t2209_non_business_tax_paid = float(st.session_state.get("t2209_non_business_tax_paid", 0.0))
t2209_net_foreign_non_business_income = float(st.session_state.get("t2209_net_foreign_non_business_income", 0.0))
t2209_net_income_override = float(st.session_state.get("t2209_net_income_override", 0.0))
t2209_basic_federal_tax_override = float(st.session_state.get("t2209_basic_federal_tax_override", 0.0))
t2036_provincial_tax_otherwise_payable_override = float(st.session_state.get("t2036_provincial_tax_otherwise_payable_override", 0.0))
cwb_basic_eligible = bool(st.session_state.get("cwb_basic_eligible", st.session_state.get("persist_cwb_basic_eligible", False)))
cwb_disability_supplement_eligible = bool(st.session_state.get("cwb_disability_supplement_eligible", st.session_state.get("persist_cwb_disability_supplement_eligible", False)))
spouse_cwb_disability_supplement_eligible = bool(st.session_state.get("spouse_cwb_disability_supplement_eligible", st.session_state.get("persist_spouse_cwb_disability_supplement_eligible", False)))
canada_workers_benefit = float(st.session_state.get("canada_workers_benefit", st.session_state.get("persist_canada_workers_benefit", 0.0)))
canada_training_credit_limit_available = float(st.session_state.get("canada_training_credit_limit_available", 0.0))
canada_training_credit = float(st.session_state.get("canada_training_credit", 0.0))
medical_expense_supplement = float(st.session_state.get("medical_expense_supplement", 0.0))
other_federal_refundable_credits = float(st.session_state.get("other_federal_refundable_credits", 0.0))
manual_provincial_refundable_credits = float(st.session_state.get("manual_provincial_refundable_credits", 0.0))
refundable_credits = float(st.session_state.get("refundable_credits", 0.0))
refundable_credits_engine_total = (
    canada_workers_benefit
    + canada_training_credit
    + medical_expense_supplement
    + other_federal_refundable_credits
    + manual_provincial_refundable_credits
    + refundable_credits
)
ontario_fertility_treatment_expenses = float(st.session_state.get("ontario_fertility_treatment_expenses", 0.0))
ontario_seniors_public_transit_expenses = float(st.session_state.get("ontario_seniors_public_transit_expenses", 0.0))
bc_renters_credit_eligible = bool(st.session_state.get("bc_renters_credit_eligible", st.session_state.get("persist_bc_renters_credit_eligible", False)))
bc_home_renovation_expenses = float(st.session_state.get("bc_home_renovation_expenses", 0.0))
bc_home_renovation_eligible = bool(st.session_state.get("bc_home_renovation_eligible", st.session_state.get("persist_bc_home_renovation_eligible", False)))
sk_fertility_treatment_expenses = float(st.session_state.get("sk_fertility_treatment_expenses", 0.0))
pe_volunteer_credit_eligible = bool(st.session_state.get("pe_volunteer_credit_eligible", st.session_state.get("persist_pe_volunteer_credit_eligible", False)))
mb479_personal_tax_credit = float(st.session_state.get("mb479_personal_tax_credit", 0.0))
mb479_homeowners_affordability_credit = float(st.session_state.get("mb479_homeowners_affordability_credit", 0.0))
mb479_renters_affordability_credit = float(st.session_state.get("mb479_renters_affordability_credit", 0.0))
mb479_seniors_school_rebate = float(st.session_state.get("mb479_seniors_school_rebate", 0.0))
mb479_primary_caregiver_credit = float(st.session_state.get("mb479_primary_caregiver_credit", 0.0))
mb479_fertility_treatment_expenses = float(st.session_state.get("mb479_fertility_treatment_expenses", 0.0))
ns479_volunteer_credit = float(st.session_state.get("ns479_volunteer_credit", 0.0))
ns479_childrens_sports_arts_credit = float(st.session_state.get("ns479_childrens_sports_arts_credit", 0.0))
nb_political_contribution_credit = float(st.session_state.get("nb_political_contribution_credit", 0.0))
nb_small_business_investor_credit = float(st.session_state.get("nb_small_business_investor_credit", 0.0))
nb_lsvcc_credit = float(st.session_state.get("nb_lsvcc_credit", 0.0))
nb_seniors_home_renovation_expenses = float(st.session_state.get("nb_seniors_home_renovation_expenses", 0.0))
nl_political_contribution_credit = float(st.session_state.get("nl_political_contribution_credit", 0.0))
nl_direct_equity_credit = float(st.session_state.get("nl_direct_equity_credit", 0.0))
nl_resort_property_credit = float(st.session_state.get("nl_resort_property_credit", 0.0))
nl_venture_capital_credit = float(st.session_state.get("nl_venture_capital_credit", 0.0))
nl_unused_venture_capital_credit = float(st.session_state.get("nl_unused_venture_capital_credit", 0.0))
nl479_other_refundable_credits = float(st.session_state.get("nl479_other_refundable_credits", 0.0))
income_tax_withheld = float(st.session_state.get("income_tax_withheld", 0.0))
cpp_withheld = float(st.session_state.get("cpp_withheld", 0.0))
ei_withheld = float(st.session_state.get("ei_withheld", 0.0))
installments_paid = float(st.session_state.get("installments_paid", 0.0))
other_payments = float(st.session_state.get("other_payments", 0.0))

render_flow_stepper(current_step)

calculate_clicked = False
reset_clicked = False

if current_step == 1:
    st.markdown("### 1) Slips")
    st.info(
        "Start here first. If you only have slips like T4, T3, T4PS, or T2202, this may already cover most of your return."
    )
    st.caption(
        "Open the matching slip tab, copy the box amounts exactly as shown, and leave anything missing at 0. Example: T4 Box 14 and Box 22, or the taxable dividend amount shown on a T5."
    )
    wizard_records = render_slip_wizard_tabs(SLIP_WIZARD_CONFIGS)
    st.caption("T4 Box 20 reduces current-year taxable income. T4 Box 52 and T4PS Box 41 are reference-only for this estimate.")
    t4_wizard_records = wizard_records["t4_wizard"]
    t4a_wizard_records = wizard_records["t4a_wizard"]
    t5_wizard_records = wizard_records["t5_wizard"]
    t3_wizard_records = wizard_records["t3_wizard"]
    t4ps_wizard_records = wizard_records["t4ps_wizard"]
    t2202_wizard_records = wizard_records["t2202_wizard"]
    st.session_state["persist_t4_wizard"] = t4_wizard_records
    st.session_state["persist_t4a_wizard"] = t4a_wizard_records
    st.session_state["persist_t5_wizard"] = t5_wizard_records
    st.session_state["persist_t3_wizard"] = t3_wizard_records
    st.session_state["persist_t4ps_wizard"] = t4ps_wizard_records
    st.session_state["persist_t2202_wizard"] = t2202_wizard_records
    nav_col1, nav_col2 = st.columns([1, 1])
    with nav_col2:
        if st.button("Next", key="next_step_1", use_container_width=True):
            st.session_state["current_flow_step"] = 2
            st.rerun()

if current_step == 2:
    st.markdown("### 2) Property and Capital Schedules")
    st.caption("Only open this if you have rental properties, real estate sales, share sales, crypto, or other capital-property activity. If none of these apply, you can go straight to Next.")
    with st.expander("Rental", expanded=False):
        st.caption("Open this only if you have rental income or rental expenses.")
        rental_schedule_df = render_record_card_editor(
        "Rental Properties",
        "rental_schedules",
        [
            {
                "id": "property_label",
                "label": "Property Label",
                "type": "text",
                "placeholder": "e.g. Toronto condo or Ottawa duplex",
            },
            {"id": "gross_rent", "label": "Gross Rents", "step": 100.0},
            {"id": "advertising", "label": "Advertising", "step": 100.0},
            {"id": "insurance", "label": "Insurance", "step": 100.0},
            {"id": "interest_bank_charges", "label": "Interest and Bank Charges", "step": 100.0},
            {"id": "property_taxes", "label": "Property Taxes", "step": 100.0},
            {"id": "utilities", "label": "Utilities", "step": 100.0},
            {"id": "repairs_maintenance", "label": "Repairs and Maintenance", "step": 100.0},
            {"id": "management_admin", "label": "Management and Administration", "step": 100.0},
            {"id": "travel", "label": "Travel", "step": 100.0},
            {"id": "office_expenses", "label": "Office Expenses", "step": 100.0},
            {"id": "other_expenses", "label": "Other Expenses", "step": 100.0},
            {"id": "cca", "label": "CCA", "step": 100.0},
        ],
        "Enter one card per property. The app totals the main T776 expense categories and then subtracts CCA.",
    )
    with st.expander("Capital Gains", expanded=False):
        st.caption("Open this only if you sold shares, real estate, crypto, or other capital property.")
        capital_schedule_df = render_record_card_editor(
        "Capital Gains Schedule",
        "capital_gain_schedules",
        [
            {
                "id": "description",
                "label": "Description",
                "type": "text",
                "placeholder": "e.g. ABC shares or rental property sale",
            },
            {
                "id": "property_type",
                "label": "Property Type",
                "type": "select",
                "options": [
                    "Publicly traded shares",
                    "Mutual funds / ETF",
                    "Real estate",
                    "Crypto asset",
                    "Other capital property",
                ],
                "value": "Publicly traded shares",
            },
            {"id": "proceeds", "label": "Proceeds of Disposition", "step": 100.0},
            {"id": "acb", "label": "Adjusted Cost Base", "step": 100.0},
            {"id": "outlays", "label": "Outlays and Expenses", "step": 100.0},
        ],
        "Enter one row per disposition. Current-year gains and losses are netted before the 50% inclusion rate is applied.",
    )
    nav_col1, nav_col2 = st.columns([1, 1])
    with nav_col1:
        if st.button("Back", key="back_step_2", use_container_width=True):
            st.session_state["current_flow_step"] = 1
            st.rerun()
    with nav_col2:
        if st.button("Next", key="next_step_2", use_container_width=True):
            st.session_state["current_flow_step"] = 3
            st.rerun()

t4_wizard_df = build_wizard_df(t4_wizard_records, SLIP_WIZARD_CONFIGS[0]["columns"])
t4a_wizard_df = build_wizard_df(t4a_wizard_records, SLIP_WIZARD_CONFIGS[1]["columns"])
t5_wizard_df = build_wizard_df(t5_wizard_records, SLIP_WIZARD_CONFIGS[2]["columns"])
t3_wizard_df = build_wizard_df(t3_wizard_records, SLIP_WIZARD_CONFIGS[3]["columns"])
t4ps_wizard_df = build_wizard_df(t4ps_wizard_records, SLIP_WIZARD_CONFIGS[4]["columns"])
t2202_wizard_df = build_wizard_df(t2202_wizard_records, SLIP_WIZARD_CONFIGS[5]["columns"])
t4_wizard_totals = t4_wizard_df.sum(numeric_only=True)
t4a_wizard_totals = t4a_wizard_df.sum(numeric_only=True)
t5_wizard_totals = t5_wizard_df.sum(numeric_only=True)
t3_wizard_totals = t3_wizard_df.sum(numeric_only=True)
t4ps_wizard_totals = t4ps_wizard_df.sum(numeric_only=True)
t2202_wizard_totals = t2202_wizard_df.sum(numeric_only=True)
t2202_tuition_total = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)) or float(
    t2202_wizard_totals.get("box23_session_tuition", 0.0)
)
t4_reference_box24_total = float(t4_wizard_totals.get("box24_ei_insurable_earnings", 0.0))
t4_reference_box26_total = float(t4_wizard_totals.get("box26_cpp_pensionable_earnings", 0.0))
t4_reference_box52_total = float(t4_wizard_totals.get("box52_pension_adjustment", 0.0))
rental_schedule_numeric_df = coerce_editor_df(
    rental_schedule_df.copy(),
    [
        "gross_rent",
        "advertising",
        "insurance",
        "interest_bank_charges",
        "property_taxes",
        "utilities",
        "repairs_maintenance",
        "management_admin",
        "travel",
        "office_expenses",
        "other_expenses",
        "cca",
    ],
)
rental_schedule_work_df = rental_schedule_numeric_df.copy()
if "property_label" not in rental_schedule_work_df.columns:
    rental_schedule_work_df["property_label"] = ""
rental_schedule_work_df["expense_total_before_cca"] = (
    rental_schedule_work_df["advertising"]
    + rental_schedule_work_df["insurance"]
    + rental_schedule_work_df["interest_bank_charges"]
    + rental_schedule_work_df["property_taxes"]
    + rental_schedule_work_df["utilities"]
    + rental_schedule_work_df["repairs_maintenance"]
    + rental_schedule_work_df["management_admin"]
    + rental_schedule_work_df["travel"]
    + rental_schedule_work_df["office_expenses"]
    + rental_schedule_work_df["other_expenses"]
)
rental_schedule_work_df["net_rental_income"] = (
    rental_schedule_work_df["gross_rent"]
    - rental_schedule_work_df["expense_total_before_cca"]
    - rental_schedule_work_df["cca"]
)
capital_schedule_numeric_df = coerce_editor_df(capital_schedule_df.copy(), ["proceeds", "acb", "outlays"])
capital_schedule_work_df = capital_schedule_numeric_df.copy()
if "description" not in capital_schedule_work_df.columns:
    capital_schedule_work_df["description"] = ""
if "property_type" not in capital_schedule_work_df.columns:
    capital_schedule_work_df["property_type"] = "Other capital property"
t776_gross_rents = float(rental_schedule_work_df["gross_rent"].sum())
t776_advertising = float(rental_schedule_work_df["advertising"].sum())
t776_insurance = float(rental_schedule_work_df["insurance"].sum())
t776_interest_bank_charges = float(rental_schedule_work_df["interest_bank_charges"].sum())
t776_property_taxes = float(rental_schedule_work_df["property_taxes"].sum())
t776_utilities = float(rental_schedule_work_df["utilities"].sum())
t776_repairs_maintenance = float(rental_schedule_work_df["repairs_maintenance"].sum())
t776_management_admin = float(rental_schedule_work_df["management_admin"].sum())
t776_travel = float(rental_schedule_work_df["travel"].sum())
t776_office_expenses = float(rental_schedule_work_df["office_expenses"].sum())
t776_other_expenses = float(rental_schedule_work_df["other_expenses"].sum())
t776_total_expenses_before_cca = float(rental_schedule_work_df["expense_total_before_cca"].sum())
t776_cca = float(rental_schedule_work_df["cca"].sum())
t776_net_rental_income = float(rental_schedule_work_df["net_rental_income"].sum())
capital_schedule_work_df["gain_or_loss"] = (
    capital_schedule_work_df["proceeds"] - capital_schedule_work_df["acb"] - capital_schedule_work_df["outlays"]
)
capital_schedule_work_df["capital_gain"] = capital_schedule_work_df["gain_or_loss"].clip(lower=0.0)
capital_schedule_work_df["capital_loss"] = (-capital_schedule_work_df["gain_or_loss"]).clip(lower=0.0)
capital_schedule_work_df["taxable_capital_gain"] = capital_schedule_work_df["capital_gain"] * 0.5
capital_schedule_work_df["allowable_capital_loss"] = capital_schedule_work_df["capital_loss"] * 0.5
t4ps_box34_capital_amount = float(t4ps_wizard_totals.get("box34_capital_gains_or_losses", 0.0))
t3_box21_capital_amount = float(t3_wizard_totals.get("box21_capital_gains", 0.0))
t4ps_box41_epsp_contributions = float(t4ps_wizard_totals.get("box41_epsp_contributions", 0.0))
schedule3_proceeds_total = float(capital_schedule_work_df["proceeds"].sum())
schedule3_acb_total = float(capital_schedule_work_df["acb"].sum())
schedule3_outlays_total = float(capital_schedule_work_df["outlays"].sum())
schedule3_gross_capital_gains = (
    float(capital_schedule_work_df["capital_gain"].sum())
    + max(0.0, t4ps_box34_capital_amount)
    + max(0.0, t3_box21_capital_amount)
)
schedule3_gross_capital_losses = (
    float(capital_schedule_work_df["capital_loss"].sum())
    + max(0.0, -t4ps_box34_capital_amount)
    + max(0.0, -t3_box21_capital_amount)
)
schedule3_net_capital_gain_or_loss = schedule3_gross_capital_gains - schedule3_gross_capital_losses
schedule3_taxable_capital_gains = max(0.0, schedule3_net_capital_gain_or_loss * 0.5)
schedule3_allowable_capital_loss = max(0.0, -schedule3_net_capital_gain_or_loss * 0.5)
employment_income = employment_income_manual + float(t4_wizard_totals.get("box14_employment_income", 0.0))
pension_income = (
    pension_income_manual
    + float(t4a_wizard_totals.get("box16_pension", 0.0))
    + float(t3_wizard_totals.get("box31_pension_income", 0.0))
)
other_income = (
    other_income_manual
    + rrsp_rrif_income_manual
    + float(t4a_wizard_totals.get("box18_lump_sum", 0.0))
    + float(t4a_wizard_totals.get("box28_other_income", 0.0))
    + float(t3_wizard_totals.get("box26_other_income", 0.0))
    + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0))
)
net_rental_income = manual_net_rental_income + t776_net_rental_income
taxable_capital_gains = manual_taxable_capital_gains + schedule3_taxable_capital_gains
interest_income = interest_income_manual + float(t5_wizard_totals.get("box13_interest", 0.0))
t5_eligible_dividends_taxable += float(t5_wizard_totals.get("box25_eligible_dividends_taxable", 0.0))
t5_eligible_dividends_taxable += float(t4ps_wizard_totals.get("box31_eligible_dividends_taxable", 0.0))
t5_non_eligible_dividends_taxable += float(t5_wizard_totals.get("box11_non_eligible_dividends_taxable", 0.0))
t5_non_eligible_dividends_taxable += float(t4ps_wizard_totals.get("box25_non_eligible_dividends_taxable", 0.0))
t5_federal_dividend_credit += float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0))
t5_federal_dividend_credit += float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0))
t5_federal_dividend_credit += float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0))
t5_federal_dividend_credit += float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0))
t3_eligible_dividends_taxable += float(t3_wizard_totals.get("box50_eligible_dividends_taxable", 0.0))
t3_non_eligible_dividends_taxable += float(t3_wizard_totals.get("box32_non_eligible_dividends_taxable", 0.0))
t3_federal_dividend_credit += float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0))
t3_federal_dividend_credit += float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0))
foreign_income += float(t5_wizard_totals.get("box15_foreign_income", 0.0))
foreign_income += float(t3_wizard_totals.get("box25_foreign_income", 0.0))
foreign_income += float(t4ps_wizard_totals.get("box37_foreign_non_business_income", 0.0))
foreign_tax_paid += float(t5_wizard_totals.get("box16_foreign_tax_paid", 0.0))
foreign_tax_paid += float(t3_wizard_totals.get("box34_foreign_tax_paid", 0.0))
medical_expenses_eligible = float(st.session_state.get("medical_expenses_eligible", 0.0))
income_tax_withheld_total = (
    income_tax_withheld
    + float(t4_wizard_totals.get("box22_tax_withheld", 0.0))
    + float(t4a_wizard_totals.get("box22_tax_withheld", 0.0))
)
cpp_withheld_total = cpp_withheld + float(t4_wizard_totals.get("box16_cpp", 0.0))
ei_withheld_total = ei_withheld + float(t4_wizard_totals.get("box18_ei", 0.0))

if current_step == 3:
    st.markdown("### 3) Income and Investment")
    st.caption("Most users can skip this section if all of their income is already covered by slips. Use it only for extra income, manual additions, or when you want a clearer worksheet trail.")
    with st.expander("Common Income", expanded=False):
        st.caption("Open this only if you need income not already covered by slips.")
        income_col1, income_col2, income_col3 = st.columns(3)
        employment_income_manual = number_input("Manual Employment Income", "employment_income", 1000.0)
        pension_income_manual = number_input("Manual Pension / Annuity Income", "pension_income", 500.0)
        rrsp_rrif_income_manual = number_input(
            "Manual RRSP / RRIF Income",
            "rrsp_rrif_income",
            500.0,
            "Use this for taxable RRSP/RRIF withdrawals or similar line 12800-style income not already captured elsewhere.",
        )
        other_income_manual = number_input("Manual Other Taxable Income", "other_income", 500.0)
        manual_net_rental_income = number_input(
            "Manual Additional Net Rental Income",
            "net_rental_income",
            500.0,
            "Use this only for net rental income not already entered through the T776 property cards above.",
        )
        manual_taxable_capital_gains = number_input(
            "Manual Additional Taxable Capital Gains",
            "taxable_capital_gains",
            500.0,
            "Use this only for taxable capital gains not already captured in Schedule 3 cards or T4PS box 34.",
        )
        interest_income_manual = number_input(
            "Manual Interest / Investment Income",
            "interest_income",
            100.0,
            "Line 12100-style interest or other investment income not already captured by T5/T3 slips.",
        )
        eligible_dividends = number_input(
            "Eligible Dividends (cash received, before gross-up)",
            "eligible_dividends",
            100.0,
            "Enter the actual cash dividend received. Do not gross this up yourself. Example: if you received $100 cash, enter $100, not $138.",
        )
        non_eligible_dividends = number_input(
            "Non-Eligible Dividends (cash received, before gross-up)",
            "non_eligible_dividends",
            100.0,
            "Enter the actual cash dividend received. Do not gross this up yourself.",
        )

    with st.expander("Dividend Details", expanded=False):
        st.caption("Open this only if you need to review or adjust dividend slip amounts.")
        div_col1, div_col2, div_col3 = st.columns(3)
        t5_eligible_dividends_taxable = number_input(
            "T5 Eligible Dividends Taxable Amount (grossed-up slip amount)",
            "t5_eligible_dividends_taxable",
            100.0,
            "Use the taxable amount shown on the slip, not the cash amount. If you already entered a manual cash dividend above for the same amount, do not enter it again here.",
        )
        t5_non_eligible_dividends_taxable = number_input(
            "T5 Other Than Eligible Dividends Taxable Amount (grossed-up slip amount)",
            "t5_non_eligible_dividends_taxable",
            100.0,
            "Use the taxable amount shown on the slip. Do not add the same dividend again as a manual cash amount above.",
        )
        t5_federal_dividend_credit = number_input(
            "T5 Federal Dividend Tax Credit",
            "t5_federal_dividend_credit",
            10.0,
            "If your T5/T3 slips already show the federal dividend tax credit, enter it here to override auto-estimation for those slips.",
        )
        t3_eligible_dividends_taxable = number_input(
            "T3 Eligible Dividends Taxable Amount (grossed-up slip amount)",
            "t3_eligible_dividends_taxable",
            100.0,
            "Use the taxable amount from the T3 slip. Skip this if the amount is already captured through the slip wizard.",
        )
        t3_non_eligible_dividends_taxable = number_input(
            "T3 Other Than Eligible Dividends Taxable Amount (grossed-up slip amount)",
            "t3_non_eligible_dividends_taxable",
            100.0,
            "Use the taxable amount from the T3 slip. Skip this if the amount is already captured through the slip wizard.",
        )
        t3_federal_dividend_credit = number_input(
            "T3 Federal Dividend Tax Credit",
            "t3_federal_dividend_credit",
            10.0,
        )

    employment_income = (
        employment_income_manual
        + float(t4_wizard_totals.get("box14_employment_income", 0.0))
    )
    pension_income = (
        pension_income_manual
        + float(t4a_wizard_totals.get("box16_pension", 0.0))
        + float(t3_wizard_totals.get("box31_pension_income", 0.0))
    )
    other_income = (
        other_income_manual
        + rrsp_rrif_income_manual
        + float(t4a_wizard_totals.get("box18_lump_sum", 0.0))
        + float(t4a_wizard_totals.get("box28_other_income", 0.0))
        + float(t3_wizard_totals.get("box26_other_income", 0.0))
        + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0))
    )
    net_rental_income = manual_net_rental_income + t776_net_rental_income
    taxable_capital_gains = manual_taxable_capital_gains + schedule3_taxable_capital_gains
    interest_income = (
        interest_income_manual
        + float(t5_wizard_totals.get("box13_interest", 0.0))
    )
    federal_dividend_credit_slip_total = (
        float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0))
        + float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0))
        + float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0))
        + float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0))
        + float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0))
        + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0))
    )

    t4_reference_box24_total = (
        float(t4_wizard_totals.get("box24_ei_insurable_earnings", 0.0))
    )
    t4_reference_box26_total = (
        float(t4_wizard_totals.get("box26_cpp_pensionable_earnings", 0.0))
    )
    t4_reference_box52_total = (
        float(t4_wizard_totals.get("box52_pension_adjustment", 0.0))
    )
    with st.expander("Advanced Totals and T4 Reference", expanded=False):
        st.dataframe(
            build_currency_df(
                [
                    {"Group": "Income Totals", "Item": "Employment incl. T4", "Amount": employment_income},
                    {"Group": "Income Totals", "Item": "Pension incl. T4A", "Amount": pension_income},
                    {"Group": "Income Totals", "Item": "RRSP / RRIF Income", "Amount": rrsp_rrif_income_manual},
                    {"Group": "Income Totals", "Item": "Other incl. T4A", "Amount": other_income},
                    {"Group": "Income Totals", "Item": "Interest incl. T5/T3", "Amount": interest_income},
                    {"Group": "Income Totals", "Item": "Net Rental incl. T776", "Amount": net_rental_income},
                    {
                        "Group": "Income Totals",
                        "Item": "Taxable Capital Gains incl. Schedule 3",
                        "Amount": taxable_capital_gains,
                    },
                    {
                        "Group": "Income Totals",
                        "Item": "Current-Year Allowable Capital Loss",
                        "Amount": schedule3_allowable_capital_loss,
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T4 Income",
                        "Amount": float(t4_wizard_totals.get("box14_employment_income", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T4 Tax Withheld",
                        "Amount": float(t4_wizard_totals.get("box22_tax_withheld", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T4 RPP",
                        "Amount": float(t4_wizard_totals.get("box20_rpp", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard Union Dues",
                        "Amount": float(t4_wizard_totals.get("box44_union_dues", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T4A Pension",
                        "Amount": float(t4a_wizard_totals.get("box16_pension", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T5 Interest",
                        "Amount": float(t5_wizard_totals.get("box13_interest", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Federal Dividend Credit From Slip Boxes",
                        "Amount": federal_dividend_credit_slip_total,
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T3 Other Income",
                        "Amount": float(t3_wizard_totals.get("box26_other_income", 0.0)),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T3 Box 21 Capital Gains",
                        "Amount": t3_box21_capital_amount,
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "Wizard T2202 Tuition",
                        "Amount": max(
                            float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)),
                            float(t2202_wizard_totals.get("box23_session_tuition", 0.0)),
                        ),
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "T4PS Box 34 Capital Gain/Loss",
                        "Amount": t4ps_box34_capital_amount,
                    },
                    {
                        "Group": "Slip Totals",
                        "Item": "T4PS Box 41 EPSP Contributions (Reference)",
                        "Amount": t4ps_box41_epsp_contributions,
                    },
                ],
                ["Amount"],
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.dataframe(
            build_currency_df(
                [
                    {
                        "Item": "T4 Box 24 EI Insurable Earnings",
                        "Amount": t4_reference_box24_total,
                    },
                    {
                        "Item": "T4 Box 26 CPP Pensionable Earnings",
                        "Amount": t4_reference_box26_total,
                    },
                    {
                        "Item": "T4 Box 52 Pension Adjustment",
                        "Amount": t4_reference_box52_total,
                    },
                ],
                ["Amount"],
            ),
            use_container_width=True,
            hide_index=True,
        )
    nav_col1, nav_col2 = st.columns([1, 1])
    with nav_col1:
        if st.button("Back", key="back_step_3", use_container_width=True):
            st.session_state["current_flow_step"] = 2
            st.rerun()
    with nav_col2:
        if st.button("Next", key="next_step_3", use_container_width=True):
            st.session_state["current_flow_step"] = 4
            st.rerun()

if current_step == 4:
    st.markdown("### 4) Deductions")
    st.caption("Use this section only if you have deductions that reduce income, such as RRSP or FHSA contributions, moving expenses, child care, support payments, or investment carrying charges. If you only have slips and no extra deductions, you can usually skip it.")
    with st.expander("Registered Plans and Payroll", expanded=False):
        st.caption("Open this only if you are claiming RRSP, FHSA, RPP, or dues.")
        ded_col1, ded_col2, ded_col3 = st.columns(3)
        rrsp_deduction = number_input(
            "RRSP Deduction Claimed This Year (line 20800)",
            "rrsp_deduction",
            500.0,
            "Enter the amount you are claiming as a deduction this year, not just the amount contributed if you plan to carry some of it forward.",
        )
        fhsa_deduction = number_input(
            "FHSA Deduction Claimed This Year (line 20805)",
            "fhsa_deduction",
            500.0,
            "Enter the amount you are claiming this year. If you contributed but are not deducting the full amount now, enter only the part claimed.",
        )
        rpp_contribution = number_input("RPP Contribution", "rpp_contribution", 500.0)
        union_dues = number_input("Union / Professional Dues (line 22200)", "union_dues", 100.0)

    with st.expander("Family, Work, and Moving", expanded=False):
        st.caption("Open this only if you have child care, moving, or support deductions.")
        ded_col4, ded_col5, ded_col6 = st.columns(3)
        child_care_expenses = number_input("Child Care Expenses (line 22100)", "child_care_expenses", 100.0)
        moving_expenses = number_input("Moving Expenses (line 21900)", "moving_expenses", 100.0)
        support_payments_deduction = number_input("Deductible Support Payments (line 22000)", "support_payments_deduction", 100.0)

    with st.expander("Investment, Employment, and Carryforwards", expanded=False):
        st.caption("Open this only if you have carrying charges, employment expenses, or loss carryforwards.")
        ded_col7, ded_col8, ded_col9 = st.columns(3)
        carrying_charges = number_input(
            "Carrying Charges / Investment Interest",
            "carrying_charges",
            100.0,
            "Use this for deductible investment carrying charges or interest. Do not include personal credit-card or mortgage interest.",
        )
        other_employment_expenses = number_input(
            "Other Employment Expenses (line 22900)",
            "other_employment_expenses",
            100.0,
            "Use this for deductible employment expenses not already included elsewhere.",
        )
        other_deductions = number_input(
            "Other Deductions",
            "other_deductions",
            100.0,
            "Use this only for deductible amounts not already covered above so you do not double count them.",
        )
        net_capital_loss_carryforward = number_input(
            "Net Capital Loss Carryforward",
            "net_capital_loss_carryforward",
            100.0,
            "Line 25300-style deduction against taxable income.",
        )
        other_loss_carryforward = number_input(
            "Other Loss Carryforward",
            "other_loss_carryforward",
            100.0,
        )
    nav_col1, nav_col2 = st.columns([1, 1])
    with nav_col1:
        if st.button("Back", key="back_step_4", use_container_width=True):
            st.session_state["current_flow_step"] = 3
            st.rerun()
    with nav_col2:
        if st.button("Next", key="next_step_4", use_container_width=True):
            st.session_state["current_flow_step"] = 5
            st.rerun()
rpp_contribution += float(t4_wizard_totals.get("box20_rpp", 0.0))
union_dues += float(t4_wizard_totals.get("box44_union_dues", 0.0))

if current_step == 5:
    st.markdown("### 5) Credits, Carryforwards, and Special Cases")
    st.caption("Most users only need one or two parts of this section. Start with the common items first and leave the rest alone unless a slip, receipt, or worksheet clearly points you there.")
    step5_render_optimization_checkpoint(
        step5_build_optimization_preview(
            session_state=st.session_state,
            t2202_wizard_totals=t2202_wizard_totals,
            t4_wizard_totals=t4_wizard_totals,
            deduction_preview_total=(
                rrsp_deduction
                + fhsa_deduction
                + rpp_contribution
                + union_dues
                + child_care_expenses
                + moving_expenses
                + support_payments_deduction
                + carrying_charges
                + other_employment_expenses
                + other_deductions
            ),
            balance_owing_preview=0.0,
        ),
        step5_build_checkpoint_suggestions(
            session_state=st.session_state,
            t2202_wizard_totals=t2202_wizard_totals,
        ),
        format_currency=format_currency,
    )
    step5_section_statuses = step5_build_section_statuses(
        session_state=st.session_state,
        t2202_wizard_totals=t2202_wizard_totals,
        province_name=province_name,
    )
    with st.expander("Common Credits You Might Claim", expanded=False):
        st.caption("Should you open this? Yes if you paid tuition, student loan interest, medical expenses, or made donations. If none of these apply, you can usually skip this section.")
        step5_render_section_intro(step5_section_statuses["common_credits"])
        spouse_amount_claim = number_input(
            "Manual spouse / common-law claim amount only if you are overriding the auto estimate",
            "spouse_amount_claim",
            100.0,
            "Auto by default. Leave at 0 if you want the app to estimate this from the household information. Enter an amount only if you are overriding it manually.",
        )
        eligible_dependant_claim = number_input(
            "Manual eligible dependant claim amount only if you are overriding the auto estimate",
            "eligible_dependant_claim",
            100.0,
            "Auto by default. Leave at 0 unless you already worked out a different claim amount and want to override the estimate.",
        )
        age_amount_claim = number_input(
            "Age amount claim base if this applies to you",
            "age_amount_claim",
            100.0,
            "Manual only if needed. Enter the claim base only if this applies and you want it included in the estimate.",
        )
        t2202_tuition_total = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)) or float(t2202_wizard_totals.get("box23_session_tuition", 0.0))
        student_loan_interest = number_input(
            "Student loan interest paid",
            "student_loan_interest",
            50.0,
            "Enter only the eligible student loan interest amount you actually paid.",
        )
        medical_expenses_eligible = number_input(
            "Manual medical claim amount only if you are overriding the auto estimate",
            "medical_expenses_eligible",
            100.0,
            "Auto by default. Leave at 0 if you want the app to calculate the medical claim from the expenses paid below. Enter an amount only if you already worked it out manually.",
        )
        medical_expenses_paid = number_input(
            "Medical expenses paid",
            "medical_expenses_paid",
            100.0,
            "Best default field for most users. Enter the amount you paid, and the app will apply the 2025 threshold automatically.",
        )
        charitable_donations = number_input(
            "Charitable donations",
            "charitable_donations",
            100.0,
            "Enter regular charitable donations here. Use the detailed donation section below only if you need extra Schedule 9 detail.",
        )
        refundable_credits = number_input(
            "Other manual refundable credits not listed elsewhere",
            "refundable_credits",
            100.0,
            "Manual only if needed. Use this only for refundable credits not already covered elsewhere in this section.",
        )
    with st.expander("Family and Household Questions", expanded=False):
        st.caption("Should you open this? Yes if spouse, children, other dependants, caregiver rules, support payments, or disability transfers may apply. If your return is only about your own slips and credits, you can usually skip it.")
        step5_render_section_intro(step5_section_statuses["household"])
        household_tabs = st.tabs(["Your Situation", "Dependant Details", "Possible Claim Conflicts"])
        with household_tabs[0]:
            with st.container(border=True):
                marital_col1, marital_col2 = st.columns(2)
                spouse_claim_enabled = checkbox_input(
                    "Should the app review whether spouse / common-law partner amount may apply?",
                    "spouse_claim_enabled",
                    container=marital_col1,
                )
                has_spouse_end_of_year = checkbox_input(
                    "Did you have a spouse or common-law partner at year end?",
                    "has_spouse_end_of_year",
                    container=marital_col1,
                )
                separated_in_year = checkbox_input(
                    "Were you separated at any point during the year?",
                    "separated_in_year",
                    container=marital_col1,
                )
                support_payments_to_spouse = checkbox_input(
                    "Did you pay support to a spouse or partner?",
                    "support_payments_to_spouse",
                    container=marital_col1,
                )
                spouse_infirm = checkbox_input(
                    "Is your spouse or partner infirm?",
                    "spouse_infirm",
                    container=marital_col2,
                )
                spouse_disability_transfer_available = checkbox_input(
                    "Does your spouse or partner have an unused disability amount available to transfer?",
                    "spouse_disability_transfer_available",
                    help_text="Check if the spouse/common-law partner has an unused disability amount transfer available to claim.",
                    container=marital_col2,
                )
                spouse_disability_transfer_available_amount = number_input(
                    "Unused spouse / partner disability amount available to transfer",
                    "spouse_disability_transfer_available_amount",
                    100.0,
                    "Manual only if needed. Enter the amount available to transfer before any claim is made.",
                )
                spouse_net_income = number_input(
                    "What was your spouse / partner's net income?",
                    "spouse_net_income",
                    100.0,
                    "Used to estimate the spouse amount if you are claiming it.",
                )
        with household_tabs[1]:
            with st.container(border=True):
                dep_col1, dep_col2 = st.columns(2)
                eligible_dependant_claim_enabled = checkbox_input(
                    "Should the app review whether an eligible dependant amount may apply?",
                    "eligible_dependant_claim_enabled",
                    container=dep_col1,
                )
                eligible_dependant_infirm = checkbox_input(
                    "Is this dependant infirm?",
                    "eligible_dependant_infirm",
                    container=dep_col1,
                )
                dependant_lived_with_you = checkbox_input(
                    "Did this dependant live with you?",
                    "dependant_lived_with_you",
                    container=dep_col1,
                )
                eligible_dependant_net_income = number_input(
                    "What was this dependant's net income?",
                    "eligible_dependant_net_income",
                    100.0,
                    "Used to estimate the eligible dependant amount if you are claiming it.",
                )
                dependant_relationship = selectbox_input(
                    "What is this dependant's relationship to you?",
                    ["Child", "Parent/Grandparent", "Other relative", "Other"],
                    "dependant_relationship",
                    "Child",
                    help_text="Used to check which household claims may be available.",
                    container=dep_col2,
                )
                dependant_category = selectbox_input(
                    "Which best describes this dependant?",
                    ["Minor child", "Adult child", "Parent/Grandparent", "Other adult relative", "Other"],
                    "dependant_category",
                    "Minor child",
                    help_text="Used for caregiver, eligible dependant, and transfer rule checks.",
                    container=dep_col2,
                )
                dependant_disability_transfer_available = checkbox_input(
                    "Does this dependant have an unused disability amount available to transfer?",
                    "dependant_disability_transfer_available",
                    help_text="Check if the dependant has an unused disability amount transfer available.",
                    container=dep_col2,
                )
                dependant_disability_transfer_available_amount = number_input(
                    "Unused dependant disability amount available to transfer",
                    "dependant_disability_transfer_available_amount",
                    100.0,
                    "Manual only if needed. Enter the amount available to transfer before any claim is made.",
                )
        with household_tabs[2]:
            with st.container(border=True):
                restrict_col1, restrict_col2 = st.columns(2)
                paid_child_support_for_dependant = checkbox_input(
                    "Did you pay child support for this dependant?",
                    "paid_child_support_for_dependant",
                    container=restrict_col1,
                )
                shared_custody_claim_agreement = checkbox_input(
                    "Is there a shared-custody arrangement that affects who can claim this dependant?",
                    "shared_custody_claim_agreement",
                    container=restrict_col1,
                )
                another_household_member_claims_dependant = checkbox_input(
                    "Is someone else already claiming this dependant-related amount?",
                    "another_household_member_claims_dependant",
                    container=restrict_col1,
                )
                another_household_member_claims_caregiver = checkbox_input(
                    "Is someone else already claiming the caregiver amount?",
                    "another_household_member_claims_caregiver",
                    container=restrict_col2,
                )
                another_household_member_claims_disability_transfer = checkbox_input(
                    "Is someone else already claiming the disability transfer?",
                    "another_household_member_claims_disability_transfer",
                    container=restrict_col2,
                )
                medical_dependant_claim_shared = checkbox_input(
                    "Is someone else already sharing or claiming this dependant's medical expenses?",
                    "medical_dependant_claim_shared",
                    container=restrict_col2,
                )
                caregiver_claim_target = selectbox_input(
                    "If a caregiver claim applies, who should the estimator try to apply it to?",
                    ["Auto", "Spouse", "Dependant"],
                    "caregiver_claim_target",
                    "Auto",
                    help_text="Use this when both spouse and dependant could qualify and you want to control which household member the caregiver claim is tied to.",
                    container=restrict_col2,
                )
                disability_transfer_source = selectbox_input(
                    "If a disability transfer applies, who should it come from?",
                    ["Auto", "Spouse", "Dependant"],
                    "disability_transfer_source",
                    "Auto",
                    help_text="Choose the source of the disability transfer when both spouse and dependant could qualify.",
                    container=restrict_col2,
                )
        with st.expander("Additional Dependants", expanded=False):
            st.caption("Should you open this? Only if you need to add a second dependant or more. Skip it if you are only checking one dependant.")
            additional_dependants_df = render_record_card_editor(
                "Additional Dependants",
                "additional_dependants",
                [
                    {"id": "dependant_label", "label": "Dependant name or label", "type": "text", "placeholder": "Dependant 2"},
                    {"id": "category", "label": "Dependant type", "type": "select", "options": ["Minor child", "Adult child", "Parent/Grandparent", "Other adult relative", "Other"]},
                    {"id": "infirm", "label": "Infirm", "type": "select", "options": ["No", "Yes"]},
                    {"id": "lived_with_you", "label": "Lived with you", "type": "select", "options": ["No", "Yes"]},
                    {"id": "caregiver_claim_amount", "label": "Caregiver claim amount", "step": 100.0},
                    {"id": "disability_transfer_available_amount", "label": "Unused disability transfer amount", "step": 100.0},
                    {"id": "medical_expenses_amount", "label": "Medical expenses for this dependant", "step": 100.0},
                    {"id": "medical_claim_shared", "label": "Medical already shared or claimed by someone else", "type": "select", "options": ["No", "Yes"]},
                ],
                "Use this only if you have more than one dependant to review. Add one row per additional dependant. These rows feed the caregiver, disability transfer, and dependant-medical calculations.",
                count_default=0,
            )
    additional_dependant_count = len(additional_dependants_df.index)
    additional_dependant_caregiver_claim_total = 0.0
    additional_dependant_disability_transfer_available_total = 0.0
    additional_dependant_medical_claim_total = 0.0
    if not additional_dependants_df.empty:
        adult_categories = {"Adult child", "Parent/Grandparent", "Other adult relative"}
        additional_dependants_df["infirm_bool"] = additional_dependants_df["infirm"].eq("Yes")
        additional_dependants_df["lived_with_you_bool"] = additional_dependants_df["lived_with_you"].eq("Yes")
        additional_dependants_df["medical_claim_shared_bool"] = additional_dependants_df["medical_claim_shared"].eq("Yes")
        additional_dependant_caregiver_claim_total = float(
            additional_dependants_df.loc[
                additional_dependants_df["infirm_bool"] & additional_dependants_df["category"].isin(adult_categories),
                "caregiver_claim_amount",
            ].sum()
        )
        additional_dependant_disability_transfer_available_total = float(
            additional_dependants_df.loc[additional_dependants_df["infirm_bool"], "disability_transfer_available_amount"].sum()
        )
        additional_dependant_medical_claim_total = float(
            additional_dependants_df.loc[
                additional_dependants_df["lived_with_you_bool"] & ~additional_dependants_df["medical_claim_shared_bool"],
                "medical_expenses_amount",
            ].sum()
        )
    with st.expander("Less Common or Manual Overrides", expanded=False):
        st.caption("Should you open this? Only if you already have a worksheet amount, need a manual override, or know a less common claim applies. If you are unsure, leave these fields alone.")
        step5_render_section_intro(step5_section_statuses["manual_overrides"])
        disability_amount_claim = number_input(
            "Disability amount claim base",
            "disability_amount_claim",
            100.0,
            "Manual only if needed. Enter the claim base if this applies and you want it included in the estimate.",
        )
        tuition_amount_claim = number_input(
            "Manual tuition amount only if you are overriding the auto estimate",
            "tuition_amount_claim",
            100.0,
            "Auto by default. Leave at 0 to use the app's current-year tuition estimate. Enter a different amount only if you are following Schedule 11 manually.",
        )
        tuition_transfer_from_spouse = number_input(
            "Tuition transfer from spouse or partner",
            "tuition_transfer_from_spouse",
            100.0,
            "Manual only if needed. Enter this only if a transfer-in amount is actually available.",
        )
        additional_federal_credits = number_input(
            "Other federal non-refundable claim amount not listed elsewhere",
            "additional_federal_credits",
            100.0,
            "Manual only if needed. Enter other federal claim amount bases from a CRA worksheet only if they are not already covered above.",
        )
        additional_provincial_credit_amount = number_input(
            f"Other {province_name} non-refundable credit not listed elsewhere",
            "additional_provincial_credit_amount",
            100.0,
            "Manual only if needed. Enter the final provincial credit amount only if you already worked it out elsewhere.",
        )
    with st.expander("Refundable Credits and Income-Tested Support", expanded=False):
        st.caption("Should you open this? Only if lower-income support, CWB, training credit, medical expense supplement, or manual refundable credits may apply. If you are unsure, leave manual amounts at 0 and use the automatic estimate where available.")
        step5_render_section_intro(step5_section_statuses["refundable"])
        refundable_col1, refundable_col2 = st.columns(2)
        canada_workers_benefit = number_input(
            "Canada Workers Benefit manual amount only if you are overriding the auto estimate",
            "canada_workers_benefit",
            100.0,
            "Auto by default. Leave at 0 to use the app's estimate. Enter your own amount only if you are following the worksheet manually.",
        )
        cwb_basic_eligible = checkbox_input(
            "Eligible for CWB",
            "cwb_basic_eligible",
            help_text="Turn this on only if CWB may apply and you want the estimator to preview it automatically.",
            container=refundable_col1,
        )
        cwb_disability_supplement_eligible = checkbox_input(
            "Eligible for CWB Disability Supplement",
            "cwb_disability_supplement_eligible",
            help_text="Turn this on only if the taxpayer qualifies for the disability tax credit and you want the estimator to preview the disability supplement path.",
            container=refundable_col1,
        )
        spouse_cwb_disability_supplement_eligible = False
        if has_spouse_end_of_year:
            spouse_cwb_disability_supplement_eligible = checkbox_input(
                "Spouse Also Eligible for CWB Disability Supplement",
                "spouse_cwb_disability_supplement_eligible",
                help_text="Used only for the family-income phaseout path in the app's 2025 disability-supplement estimate.",
                container=refundable_col1,
            )
        canada_training_credit_limit_available = number_input(
            "Canada Training Credit limit available",
            "canada_training_credit_limit_available",
            100.0,
            "Enter this only if you know your available training credit limit. The estimator uses it for the automatic training credit preview.",
        )
        canada_training_credit = number_input(
            "Canada Training Credit manual amount only if you are overriding the auto estimate",
            "canada_training_credit",
            100.0,
            "Auto by default. Leave at 0 to use the app's estimate from the training credit limit and current-year tuition claim.",
        )
        medical_expense_supplement = number_input(
            "Medical Expense Supplement manual amount only if you are overriding the auto estimate",
            "medical_expense_supplement",
            100.0,
            "Auto by default. Leave at 0 to use the app's estimate from employment income, net income, and the medical claim.",
        )
        other_federal_refundable_credits = refundable_col2.number_input(
            "Other federal refundable credits not listed elsewhere",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("other_federal_refundable_credits", 0.0)),
            key="other_federal_refundable_credits",
            help="Manual only if needed. Use this only for refundable federal amounts not already covered above.",
        )
        manual_provincial_refundable_credits = refundable_col2.number_input(
            f"Other {province_name} refundable credits not listed elsewhere",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("manual_provincial_refundable_credits", 0.0)),
            key="manual_provincial_refundable_credits",
            help=f"Manual only if needed. Use this only for {province_name} refundable amounts not already covered above.",
        )
    refundable_credits_engine_total = (
        canada_workers_benefit
        + canada_training_credit
        + medical_expense_supplement
        + other_federal_refundable_credits
        + manual_provincial_refundable_credits
        + refundable_credits
    )
    st.session_state["persist_spouse_claim_enabled"] = spouse_claim_enabled
    st.session_state["persist_has_spouse_end_of_year"] = has_spouse_end_of_year
    st.session_state["persist_separated_in_year"] = separated_in_year
    st.session_state["persist_support_payments_to_spouse"] = support_payments_to_spouse
    st.session_state["persist_spouse_infirm"] = spouse_infirm
    st.session_state["persist_spouse_disability_transfer_available"] = spouse_disability_transfer_available
    st.session_state["persist_spouse_disability_transfer_available_amount"] = spouse_disability_transfer_available_amount
    st.session_state["persist_spouse_net_income"] = spouse_net_income
    st.session_state["persist_spouse_amount_claim"] = spouse_amount_claim
    st.session_state["persist_eligible_dependant_claim_enabled"] = eligible_dependant_claim_enabled
    st.session_state["persist_eligible_dependant_infirm"] = eligible_dependant_infirm
    st.session_state["persist_dependant_lived_with_you"] = dependant_lived_with_you
    st.session_state["persist_eligible_dependant_net_income"] = eligible_dependant_net_income
    st.session_state["persist_eligible_dependant_claim"] = eligible_dependant_claim
    st.session_state["persist_dependant_relationship"] = dependant_relationship
    st.session_state["persist_dependant_category"] = dependant_category
    st.session_state["persist_dependant_disability_transfer_available"] = dependant_disability_transfer_available
    st.session_state["persist_dependant_disability_transfer_available_amount"] = dependant_disability_transfer_available_amount
    st.session_state["persist_paid_child_support_for_dependant"] = paid_child_support_for_dependant
    st.session_state["persist_shared_custody_claim_agreement"] = shared_custody_claim_agreement
    st.session_state["persist_another_household_member_claims_dependant"] = another_household_member_claims_dependant
    st.session_state["persist_another_household_member_claims_caregiver"] = another_household_member_claims_caregiver
    st.session_state["persist_another_household_member_claims_disability_transfer"] = another_household_member_claims_disability_transfer
    st.session_state["persist_medical_dependant_claim_shared"] = medical_dependant_claim_shared
    st.session_state["persist_caregiver_claim_target"] = caregiver_claim_target
    st.session_state["persist_disability_transfer_source"] = disability_transfer_source
    st.session_state["persist_cwb_basic_eligible"] = cwb_basic_eligible
    st.session_state["persist_cwb_disability_supplement_eligible"] = cwb_disability_supplement_eligible
    st.session_state["persist_spouse_cwb_disability_supplement_eligible"] = spouse_cwb_disability_supplement_eligible
    st.session_state["persist_canada_workers_benefit"] = canada_workers_benefit
    with st.expander("Province-Specific Credits and Special Schedules", expanded=False):
        st.caption("Should you open this? Only if a provincial worksheet, province-specific credit, or special schedule applies to you. If not, leave this section alone.")
        step5_render_section_intro(step5_section_statuses["province_special"])
        on_col1, on_col2, on_col3 = st.columns(3)
        ontario_caregiver_amount = on_col1.number_input(
            f"{province_name} Caregiver Claim Amount",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("provincial_caregiver_claim_amount", 0.0)),
            key="provincial_caregiver_claim_amount",
            help=PROVINCIAL_CAREGIVER_HELP.get(province, f"Enter the {province_name} caregiver or infirm dependant claim amount base if applicable."),
        )
        ontario_student_loan_interest = on_col1.number_input(
            "Ontario Student Loan Interest",
            min_value=0.0,
            step=50.0,
            value=float(st.session_state.get("ontario_student_loan_interest", 0.0)),
            key="ontario_student_loan_interest",
        )
        ontario_tuition_transfer = on_col1.number_input(
            "Ontario Tuition Transfer",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("ontario_tuition_transfer", 0.0)),
            key="ontario_tuition_transfer",
        )
        ontario_disability_transfer = on_col2.number_input(
            "Ontario Disability Transfer",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("ontario_disability_transfer", 0.0)),
            key="ontario_disability_transfer",
        )
        ontario_adoption_expenses = on_col2.number_input(
            "Ontario Adoption Expenses",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("ontario_adoption_expenses", 0.0)),
            key="ontario_adoption_expenses",
        )
        ontario_medical_dependants = on_col2.number_input(
            "Ontario Medical for Other Dependants",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("ontario_medical_dependants", 0.0)),
            key="ontario_medical_dependants",
            help="Enter medical expenses for other dependants. The Ontario limit is applied automatically for 2025.",
        )
        ontario_dependent_children_count = int(
            on_col3.number_input(
                f"{province_name} Dependent Children Count",
                min_value=0,
                step=1,
                value=int(st.session_state.get("provincial_dependent_children_count", 0)),
                key="provincial_dependent_children_count",
                help="Used for Ontario tax reduction and for other province child-based reductions where built in.",
            )
        )
        ontario_dependant_impairment_count = int(
            on_col3.number_input(
                "Ontario Impairment Dependants Count",
                min_value=0,
                step=1,
                value=int(st.session_state.get("ontario_dependant_impairment_count", 0)),
                key="ontario_dependant_impairment_count",
                help="Additional Ontario tax reduction for qualifying dependants with an impairment.",
            )
        )

    with st.expander("Foreign Income, Dividend Credits, and Manual Overrides", expanded=False):
        st.caption("Should you open this? Only if you have foreign income, foreign tax paid, or a dividend-credit amount that differs from the estimator. If your slips already cover everything, you can usually skip this.")
        step5_render_section_intro(step5_section_statuses["foreign"])
        fd_col1, fd_col2 = st.columns(2)
        foreign_income = fd_col1.number_input(
            "Manual additional foreign income not already shown on slips",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("foreign_income", 0.0)),
            key="foreign_income",
            help="Manual only if needed. Use this only for extra foreign non-business income not already captured by T5, T3, or T4PS slips. Do not repeat slip amounts here.",
        )
        foreign_tax_paid = fd_col1.number_input(
            "Manual additional foreign tax paid not already shown on slips",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.get("foreign_tax_paid", 0.0)),
            key="foreign_tax_paid",
            help="Manual only if needed. Use this only for extra foreign tax paid not already captured by T5 or T3 slips. Do not repeat slip amounts here.",
        )
        ontario_dividend_tax_credit_manual = fd_col2.number_input(
            f"{province_name} dividend tax credit manual amount only if you are overriding the auto estimate",
            min_value=0.0,
            step=50.0,
            value=float(st.session_state.get("provincial_dividend_tax_credit_manual", 0.0)),
            key="provincial_dividend_tax_credit_manual",
            help=f"Auto by default. Leave at 0 to use the auto-calculated {province_name} dividend tax credit where supported. Enter a different amount only if your worksheet shows a different result.",
        )
        st.caption("Slip amounts from T5, T3, and T4PS are already added automatically. Only enter extra amounts missing from slips.")

        with st.expander("Advanced Foreign Tax Amounts", expanded=False):
            st.caption("Should you open this? Only if you are checking T2209 or T2036 line by line. Otherwise leave these advanced overrides at 0.")
            ftc_col1, ftc_col2, ftc_col3 = st.columns(3)
            t2209_non_business_tax_paid = ftc_col1.number_input(
                "T2209 Line 1 Non-Business Tax Paid Manual Amount",
                min_value=0.0,
                step=100.0,
                value=float(st.session_state.get("t2209_non_business_tax_paid", 0.0)),
                key="t2209_non_business_tax_paid",
                help="Optional. Leave this at 0 unless you are working from the T2209 form and want to override the foreign-tax total used by the app.",
            )
            t2209_net_foreign_non_business_income = ftc_col1.number_input(
                "T2209 Line 2 Net Foreign Non-Business Income Manual Amount",
                min_value=0.0,
                step=100.0,
                value=float(st.session_state.get("t2209_net_foreign_non_business_income", 0.0)),
                key="t2209_net_foreign_non_business_income",
                help="Optional. Leave this at 0 unless you are following T2209 directly and want to override the foreign-income amount used by the app.",
            )
            t2209_net_income_override = ftc_col2.number_input(
                "T2209 Net Income Manual Amount",
                min_value=0.0,
                step=100.0,
                value=float(st.session_state.get("t2209_net_income_override", 0.0)),
                key="t2209_net_income_override",
                help="Advanced override. Leave at 0 unless you are checking the T2209 worksheet line by line.",
            )
            t2209_basic_federal_tax_override = ftc_col2.number_input(
                "T2209 Basic Federal Tax Manual Amount",
                min_value=0.0,
                step=100.0,
                value=float(st.session_state.get("t2209_basic_federal_tax_override", 0.0)),
                key="t2209_basic_federal_tax_override",
                help="Advanced override. Leave at 0 unless your own T2209 worksheet uses a different federal tax amount.",
            )
            t2036_provincial_tax_otherwise_payable_override = ftc_col3.number_input(
                "T2036 Provincial Tax Otherwise Payable Manual Amount",
                min_value=0.0,
                step=100.0,
                value=float(st.session_state.get("t2036_provincial_tax_otherwise_payable_override", 0.0)),
                key="t2036_provincial_tax_otherwise_payable_override",
                help="Optional override for the T2036 provincial tax otherwise payable amount.",
            )

    with st.expander("Detailed Donation Inputs (Advanced)", expanded=False):
        st.caption("Should you open this? Only if you need extra Schedule 9 donation detail beyond the regular donation amount above.")
        don_col1, don_col2, don_col3 = st.columns(3)
        donations_eligible_total = number_input(
            "Schedule 9 regular donations if you need to override the simpler donation field",
            "donations_eligible_total",
            100.0,
            "Auto by default. Leave at 0 to use the Charitable Donations amount above.",
        )
        ecological_cultural_gifts = number_input(
            "Ecological / Cultural Gifts",
            "ecological_cultural_gifts",
            100.0,
        )
        ecological_gifts_pre2016 = number_input(
            "Pre-2016 Ecological Gifts Included Above",
            "ecological_gifts_pre2016",
            100.0,
        )

    with st.expander("Prior-Year Carryforwards and Transfers", expanded=False):
        st.caption("Should you open this? Only if you are bringing forward amounts from an earlier year or using a transfer. Quick guide: Available = what you still have, Requested = what you want to use this year, Used = what the estimator actually applies.")
        step5_render_section_intro(step5_section_statuses["carryforwards"])
        carryforward_tabs = st.tabs(["Tuition Carryforward", "Donation Carryforward", f"{province_name} Additional Lines"])
        with carryforward_tabs[0]:
            tuition_cf_df = render_record_card_editor(
                "Tuition Carryforward by Year",
                "tuition_carryforwards",
                [
                    {"id": "tax_year", "label": "Tax Year", "step": 1.0},
                    {"id": "available_amount", "label": "Available Amount", "step": 100.0},
                    {"id": "claim_amount", "label": "Claim Amount", "step": 100.0},
                ],
                "Enter one row per prior year. Available = what remains from that year. Claim amount = what you want to use now. The estimator caps the used amount to what is actually available.",
            )
            step5_render_carryforward_mini_worksheet(
                "Tuition Carryforward",
                tuition_cf_df.to_dict("records") if not tuition_cf_df.empty else [],
                build_currency_df=build_currency_df,
                render_metric_row=render_metric_row,
            )
        with carryforward_tabs[1]:
            donation_cf_df = render_record_card_editor(
                "Donation Carryforward by Year",
                "donation_carryforwards",
                [
                    {"id": "tax_year", "label": "Tax Year", "step": 1.0},
                    {"id": "available_amount", "label": "Available Amount", "step": 100.0},
                    {"id": "claim_amount", "label": "Claim Amount", "step": 100.0},
                ],
                "Enter one row per prior year. Available = what remains from that year. Claim amount = what you want to use now. The estimator applies the allowed amount through Schedule 9.",
            )
            step5_render_carryforward_mini_worksheet(
                "Donation Carryforward",
                donation_cf_df.to_dict("records") if not donation_cf_df.empty else [],
                build_currency_df=build_currency_df,
                render_metric_row=render_metric_row,
            )
        with carryforward_tabs[2]:
            provincial_credit_lines_df = render_record_card_editor(
                f"{province_name} additional credit lines not already covered elsewhere",
                "provincial_credit_lines",
                [
                    {"id": "line_code", "label": "Line Code", "step": 1.0},
                    {"id": "amount", "label": "Amount", "step": 100.0},
                ],
                "Manual only if needed. Use this for province-specific credit lines not otherwise modelled. Amounts are added to provincial non-refundable credits.",
            )
        st.markdown("#### Province Special Schedules")
        st.caption("Open this only if a province worksheet or special provincial schedule clearly applies to you.")
        sp_col1, sp_col2, sp_col3 = st.columns(3)
    mb479_personal_tax_credit = 0.0
    mb479_homeowners_affordability_credit = 0.0
    mb479_renters_affordability_credit = 0.0
    mb479_seniors_school_rebate = 0.0
    mb479_primary_caregiver_credit = 0.0
    mb479_fertility_treatment_expenses = 0.0
    ns479_volunteer_credit = 0.0
    ns479_childrens_sports_arts_credit = 0.0
    ontario_fertility_treatment_expenses = 0.0
    ontario_seniors_public_transit_expenses = 0.0
    bc_renters_credit_eligible = False
    bc_home_renovation_expenses = 0.0
    bc_home_renovation_eligible = False
    sk_fertility_treatment_expenses = 0.0
    pe_volunteer_credit_eligible = False
    nb_political_contribution_credit = 0.0
    nb_small_business_investor_credit = 0.0
    nb_lsvcc_credit = 0.0
    nb_seniors_home_renovation_expenses = 0.0
    nl_political_contribution_credit = 0.0
    nl_direct_equity_credit = 0.0
    nl_resort_property_credit = 0.0
    nl_venture_capital_credit = 0.0
    nl_unused_venture_capital_credit = 0.0
    nl479_other_refundable_credits = 0.0

    if province == "MB":
        mb479_personal_tax_credit = number_input("MB479 Personal Tax Credit", "mb479_personal_tax_credit", 50.0)
        mb479_homeowners_affordability_credit = number_input("MB479 Homeowners Affordability Credit", "mb479_homeowners_affordability_credit", 50.0)
        mb479_renters_affordability_credit = number_input("MB479 Renters Affordability Credit", "mb479_renters_affordability_credit", 50.0)
        mb479_seniors_school_rebate = number_input("MB479 Seniors School Tax Rebate", "mb479_seniors_school_rebate", 50.0)
        mb479_primary_caregiver_credit = number_input("MB479 Primary Caregiver Tax Credit", "mb479_primary_caregiver_credit", 50.0)
        mb479_fertility_treatment_expenses = number_input(
            "MB479 Fertility Treatment Expenses",
            "mb479_fertility_treatment_expenses",
            100.0,
            "The estimator applies a 40% Manitoba fertility treatment credit, capped at $16,000.",
        )
    elif province == "NS":
        volunteer_flag = checkbox_input(
            "NS479 Volunteer Firefighter / Search and Rescue Credit",
            "ns479_volunteer_flag",
            help_text="If eligible, the app enters the fixed $500 NS479 credit.",
        )
        ns479_volunteer_credit = 500.0 if volunteer_flag else 0.0
        ns479_childrens_sports_arts_credit = number_input(
            "NS479 Children's Sports and Arts Credit",
            "ns479_childrens_sports_arts_credit",
            50.0,
            "Enter the final credit amount from your NS479 worksheet if applicable.",
        )
    elif province == "ON":
        ontario_fertility_treatment_expenses = number_input(
            "ON479 Fertility Treatment Expenses",
            "ontario_fertility_treatment_expenses",
            100.0,
            "The estimator applies the Ontario refundable fertility treatment tax credit to eligible expenses.",
        )
        ontario_seniors_public_transit_expenses = number_input(
            "ON479 Seniors' Public Transit Expenses",
            "ontario_seniors_public_transit_expenses",
            100.0,
            "The estimator applies the Ontario seniors' public transit tax credit if age 65 or older.",
        )
    elif province == "BC":
        bc_renters_credit_eligible = checkbox_input(
            "BC Renter's Tax Credit Eligible",
            "bc_renters_credit_eligible",
            help_text="Check if the taxpayer qualifies to claim the B.C. renter's tax credit.",
            container=sp_col1,
        )
        bc_home_renovation_eligible = checkbox_input(
            "BC Home Renovation Credit Eligible",
            "bc_home_renovation_eligible",
            help_text="Check if the taxpayer or qualifying household qualifies for the B.C. home renovation credit.",
            container=sp_col2,
        )
        bc_home_renovation_expenses = number_input(
            "BC Home Renovation Eligible Expenses",
            "bc_home_renovation_expenses",
            100.0,
            "The estimator applies the B.C. refundable home renovation credit to eligible expenses.",
        )
    elif province == "SK":
        sk_fertility_treatment_expenses = number_input(
            "SK479 Fertility Treatment Expenses",
            "sk_fertility_treatment_expenses",
            100.0,
            "The estimator applies the Saskatchewan refundable fertility treatment tax credit to eligible expenses.",
        )
    elif province == "PE":
        pe_volunteer_credit_eligible = checkbox_input(
            "PE Volunteer Firefighter / Search and Rescue Credit Eligible",
            "pe_volunteer_credit_eligible",
            help_text="Check if the taxpayer qualifies for the Prince Edward Island volunteer firefighter or volunteer search and rescue personnel tax credit.",
            container=sp_col1,
        )
    elif province == "NB":
        nb_political_contribution_credit = number_input("NB428 Political Contribution Credit", "nb_political_contribution_credit", 50.0)
        nb_small_business_investor_credit = number_input("NB428 Small Business Investor Credit", "nb_small_business_investor_credit", 50.0)
        nb_lsvcc_credit = number_input("NB428 Labour-Sponsored Venture Capital Credit", "nb_lsvcc_credit", 50.0)
        nb_seniors_home_renovation_expenses = number_input(
            "NB(S12) Seniors' Home Renovation Expenses",
            "nb_seniors_home_renovation_expenses",
            100.0,
            "The estimator applies the 10% refundable credit up to $10,000 of eligible expenses.",
        )
    elif province == "NL":
        nl_political_contribution_credit = number_input("NL428 Political Contribution Credit", "nl_political_contribution_credit", 50.0)
        nl_direct_equity_credit = number_input("NL428 Direct Equity Tax Credit", "nl_direct_equity_credit", 50.0)
        nl_resort_property_credit = number_input("NL428 Resort Property Investment Credit", "nl_resort_property_credit", 50.0)
        nl_venture_capital_credit = number_input("NL428 Venture Capital Credit", "nl_venture_capital_credit", 50.0)
        nl_unused_venture_capital_credit = number_input("NL428 Unused Venture Capital Credit", "nl_unused_venture_capital_credit", 50.0)
        nl479_other_refundable_credits = number_input("NL479 Other Refundable Credits", "nl479_other_refundable_credits", 50.0)
    st.session_state["persist_bc_renters_credit_eligible"] = bc_renters_credit_eligible
    st.session_state["persist_bc_home_renovation_eligible"] = bc_home_renovation_eligible
    st.session_state["persist_pe_volunteer_credit_eligible"] = pe_volunteer_credit_eligible
tuition_cf_df = coerce_editor_df(tuition_cf_df, ["tax_year", "available_amount", "claim_amount"])
donation_cf_df = coerce_editor_df(donation_cf_df, ["tax_year", "available_amount", "claim_amount"])
provincial_credit_lines_df = coerce_editor_df(provincial_credit_lines_df, ["line_code", "amount"])
tuition_carryforward_available_total = float(tuition_cf_df["available_amount"].sum())
tuition_carryforward_claim_requested = float(tuition_cf_df["claim_amount"].sum())
tuition_carryforward_claim_total = min(tuition_carryforward_available_total, tuition_carryforward_claim_requested)
tuition_carryforward_unused = max(0.0, tuition_carryforward_available_total - tuition_carryforward_claim_total)
donation_carryforward_available_total = float(donation_cf_df["available_amount"].sum())
donation_carryforward_claim_requested = float(donation_cf_df["claim_amount"].sum())
donation_carryforward_claim_total = 0.0
donation_carryforward_unused = donation_carryforward_available_total
provincial_credit_lines_total = float(provincial_credit_lines_df["amount"].sum())
if current_step == 5:
    nav_col1, nav_col2 = st.columns([1, 1])
    with nav_col1:
        if st.button("Back", key="back_step_5", use_container_width=True):
            st.session_state["current_flow_step"] = 4
            st.rerun()
    with nav_col2:
        if st.button("Next", key="next_step_5", use_container_width=True):
            st.session_state["current_flow_step"] = 6
            st.rerun()
schedule11_current_year_tuition_available = t2202_tuition_total
schedule11_current_year_claim_requested = (
    schedule11_current_year_tuition_available
    if tuition_amount_claim == 0.0
    else tuition_amount_claim
)
schedule11_current_year_claim_used = min(
    schedule11_current_year_tuition_available,
    schedule11_current_year_claim_requested,
)
schedule9_current_year_donations_available = max(donations_eligible_total, charitable_donations)
schedule9_current_year_donations_claim_requested = schedule9_current_year_donations_available
schedule9_current_year_donations_claim_used = 0.0
schedule9_current_year_donations_unused = schedule9_current_year_donations_available
schedule9_total_regular_donations_claimed = 0.0
schedule9_total_regular_donations_unused = schedule9_current_year_donations_available + donation_carryforward_available_total

if current_step == 6:
    st.markdown("### 6) Payments and Withholdings")
    st.caption("You can skip this section unless you made instalments, had extra tax deducted outside slips, or need to add other payments not already captured from your slips.")
    with st.expander("Additional Payments and Withholding", expanded=False):
        st.caption("Open this only if you made instalments or have extra payments or withholding.")
        pay_col1, pay_col2, pay_col3 = st.columns(3)
        income_tax_withheld = number_input("Other Income Tax Deducted at Source (line 43700)", "income_tax_withheld", 100.0)
        cpp_withheld = number_input(
            "CPP Withheld on Slips",
            "cpp_withheld",
            100.0,
            "Optional override reference only. The estimator still calculates CPP from income sources.",
        )
        ei_withheld = number_input(
            "EI Withheld on Slips",
            "ei_withheld",
            100.0,
            "Optional override reference only. The estimator still calculates EI from employment income.",
        )
        installments_paid = number_input("Tax Instalments Paid (line 47600)", "installments_paid", 100.0)
        other_payments = number_input("Other Tax Payments / Credits", "other_payments", 100.0)
    income_tax_withheld_total = (
        income_tax_withheld
        + float(t4_wizard_totals.get("box22_tax_withheld", 0.0))
        + float(t4a_wizard_totals.get("box22_tax_withheld", 0.0))
    )
    cpp_withheld_total = cpp_withheld + float(t4_wizard_totals.get("box16_cpp", 0.0))
    ei_withheld_total = ei_withheld + float(t4_wizard_totals.get("box18_ei", 0.0))
    render_metric_row(
        [
            ("Tax Withheld incl. Slips", income_tax_withheld_total),
            ("CPP Withheld incl. T4", cpp_withheld_total),
            ("EI Withheld incl. T4", ei_withheld_total),
        ],
        3,
    )
    nav_col1, nav_col2 = st.columns([1, 1])
    with nav_col1:
        if st.button("Back", key="back_step_6", use_container_width=True):
            st.session_state["current_flow_step"] = 5
            st.rerun()
    with nav_col2:
        if st.button("Next", key="next_step_6", use_container_width=True):
            st.session_state["current_flow_step"] = 7
            st.rerun()

t4_params = TAX_CONFIGS[tax_year]
estimator_ei_insurable_earnings = min(employment_income, t4_params["ei_max_insurable_earnings"])
estimator_cpp_pensionable_earnings = max(
    0.0,
    min(employment_income, t4_params["cpp_ympe"]) - t4_params["cpp_basic_exemption"],
)
estimated_total_income = (
    employment_income
    + pension_income
    + rrsp_rrif_income_manual
    + other_income
    + net_rental_income
    + taxable_capital_gains
    + interest_income
    + t5_eligible_dividends_taxable
    + t5_non_eligible_dividends_taxable
    + t3_eligible_dividends_taxable
    + t3_non_eligible_dividends_taxable
)
estimated_total_deductions = (
    rrsp_deduction
    + fhsa_deduction
    + rpp_contribution
    + union_dues
    + child_care_expenses
    + moving_expenses
    + support_payments_deduction
    + carrying_charges
    + other_employment_expenses
    + other_deductions
)
estimated_net_income = max(0.0, estimated_total_income - estimated_total_deductions)
schedule9_regular_limit_preview = max(0.0, estimated_net_income * 0.75)
donation_carryforward_claim_total = min(
    donation_carryforward_available_total,
    donation_carryforward_claim_requested,
    schedule9_regular_limit_preview,
)
remaining_schedule9_limit_preview = max(0.0, schedule9_regular_limit_preview - donation_carryforward_claim_total)
schedule9_current_year_donations_claim_used = min(
    schedule9_current_year_donations_available,
    schedule9_current_year_donations_claim_requested,
    remaining_schedule9_limit_preview,
)
donation_carryforward_unused = max(0.0, donation_carryforward_available_total - donation_carryforward_claim_total)
schedule9_current_year_donations_unused = max(
    0.0,
    schedule9_current_year_donations_available - schedule9_current_year_donations_claim_used,
)
schedule9_total_regular_donations_claimed = schedule9_current_year_donations_claim_used + donation_carryforward_claim_total
schedule9_total_regular_donations_unused = schedule9_current_year_donations_unused + donation_carryforward_unused
estimated_medical_claim_amount = medical_expenses_eligible
if tax_year in FEDERAL_MEDICAL_THRESHOLDS:
    estimated_medical_claim_amount = calculate_medical_claim(
        medical_expenses_paid,
        estimated_net_income,
        FEDERAL_MEDICAL_THRESHOLDS[tax_year],
    )
line_21300 = float(st.session_state.get("line_21300", 0.0))
rdsp_repayment = float(st.session_state.get("rdsp_repayment", 0.0))
universal_child_care_benefit = float(st.session_state.get("universal_child_care_benefit", 0.0))
rdsp_income = float(st.session_state.get("rdsp_income", 0.0))
spouse_line_21300 = float(st.session_state.get("spouse_line_21300", 0.0))
spouse_rdsp_repayment = float(st.session_state.get("spouse_rdsp_repayment", 0.0))
spouse_uccb = float(st.session_state.get("spouse_uccb", 0.0))
spouse_rdsp_income = float(st.session_state.get("spouse_rdsp_income", 0.0))
estimated_adjusted_net_income_for_cwb = max(
    0.0,
    estimated_net_income + line_21300 + rdsp_repayment - universal_child_care_benefit - rdsp_income,
)
estimated_spouse_adjusted_net_income_for_cwb = max(
    0.0,
    spouse_net_income + spouse_line_21300 + spouse_rdsp_repayment - spouse_uccb - spouse_rdsp_income,
)
if cwb_basic_eligible:
    auto_canada_workers_benefit_preview = calculate_canada_workers_benefit(
        tax_year=tax_year,
        working_income=employment_income,
        adjusted_net_income=estimated_adjusted_net_income_for_cwb,
        spouse_adjusted_net_income=estimated_spouse_adjusted_net_income_for_cwb,
        has_spouse=has_spouse_end_of_year,
    )
    auto_cwb_disability_supplement_preview = calculate_cwb_disability_supplement(
        tax_year=tax_year,
        adjusted_net_income=estimated_adjusted_net_income_for_cwb,
        spouse_adjusted_net_income=estimated_spouse_adjusted_net_income_for_cwb,
        has_spouse=has_spouse_end_of_year,
        is_disabled=cwb_disability_supplement_eligible,
        spouse_is_disabled=spouse_cwb_disability_supplement_eligible,
    )
else:
    auto_canada_workers_benefit_preview = {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
    auto_cwb_disability_supplement_preview = {"base_credit": 0.0, "phaseout": 0.0, "credit": 0.0}
auto_medical_expense_supplement_preview = calculate_medical_expense_supplement(
    tax_year=tax_year,
    employment_income=employment_income,
    net_income=estimated_net_income,
    medical_claim=estimated_medical_claim_amount,
)
employee_payroll_preview = estimate_employee_cpp_ei(employment_income, t4_params)
auto_payroll_overpayment_preview = calculate_payroll_overpayment_refunds(
    cpp_withheld=cpp_withheld_total,
    ei_withheld=ei_withheld_total,
    expected_cpp=employee_payroll_preview["employee_cpp_total"],
    expected_ei=employee_payroll_preview["ei"],
)
diagnostics = collect_diagnostics(
    {
        "employment_income_manual": employment_income_manual,
        "pension_income_manual": pension_income_manual,
        "manual_net_rental_income": manual_net_rental_income,
        "manual_taxable_capital_gains": manual_taxable_capital_gains,
        "manual_foreign_income": float(st.session_state.get("foreign_income", 0.0)),
        "manual_foreign_tax_paid": float(st.session_state.get("foreign_tax_paid", 0.0)),
        "tuition_amount_claim_override": tuition_amount_claim,
        "spouse_claim_enabled": spouse_claim_enabled,
        "eligible_dependant_claim_enabled": eligible_dependant_claim_enabled,
        "has_spouse_end_of_year": has_spouse_end_of_year,
        "separated_in_year": separated_in_year,
        "support_payments_to_spouse": support_payments_to_spouse,
        "dependant_lived_with_you": dependant_lived_with_you,
        "dependant_relationship": dependant_relationship,
        "dependant_category": dependant_category,
        "paid_child_support_for_dependant": paid_child_support_for_dependant,
        "shared_custody_claim_agreement": shared_custody_claim_agreement,
        "another_household_member_claims_dependant": another_household_member_claims_dependant,
        "another_household_member_claims_caregiver": another_household_member_claims_caregiver,
        "another_household_member_claims_disability_transfer": another_household_member_claims_disability_transfer,
        "medical_dependant_claim_shared": medical_dependant_claim_shared,
        "caregiver_claim_target": caregiver_claim_target,
        "disability_transfer_source": disability_transfer_source,
        "spouse_infirm": spouse_infirm,
        "spouse_disability_transfer_available": spouse_disability_transfer_available,
        "spouse_disability_transfer_available_amount": spouse_disability_transfer_available_amount,
        "eligible_dependant_infirm": eligible_dependant_infirm,
        "dependant_disability_transfer_available": dependant_disability_transfer_available,
        "dependant_disability_transfer_available_amount": dependant_disability_transfer_available_amount,
        "additional_dependant_count": float(additional_dependant_count),
        "additional_dependant_caregiver_claim_total": additional_dependant_caregiver_claim_total,
        "additional_dependant_disability_transfer_available_total": additional_dependant_disability_transfer_available_total,
        "additional_dependant_medical_claim_total": additional_dependant_medical_claim_total,
        "caregiver_claim_amount": ontario_caregiver_amount,
        "ontario_disability_transfer": ontario_disability_transfer,
        "ontario_medical_dependants": ontario_medical_dependants,
        "t4_income_total": float(t4_wizard_totals.get("box14_employment_income", 0.0)),
        "t4_tax_withheld_total": float(t4_wizard_totals.get("box22_tax_withheld", 0.0)),
        "t4_cpp_total": float(t4_wizard_totals.get("box16_cpp", 0.0)),
        "t4_ei_total": float(t4_wizard_totals.get("box18_ei", 0.0)),
        "t4a_pension_total": float(t4a_wizard_totals.get("box16_pension", 0.0)),
        "t3_pension_total": float(t3_wizard_totals.get("box31_pension_income", 0.0)),
        "schedule3_taxable_capital_gains": schedule3_taxable_capital_gains,
        "t2202_tuition_total": t2202_tuition_total,
        "t2202_months_total": float(t2202_wizard_totals.get("box21_months_part_time", 0.0)) + float(t2202_wizard_totals.get("box22_months_full_time", 0.0)) + float(t2202_wizard_totals.get("box24_total_months_part_time", 0.0)) + float(t2202_wizard_totals.get("box25_total_months_full_time", 0.0)),
        "t776_net_rental_income": t776_net_rental_income,
        "slip_foreign_income_total": float(t5_wizard_totals.get("box15_foreign_income", 0.0)) + float(t3_wizard_totals.get("box25_foreign_income", 0.0)) + float(t4ps_wizard_totals.get("box37_foreign_non_business_income", 0.0)),
        "slip_foreign_tax_paid_total": float(t5_wizard_totals.get("box16_foreign_tax_paid", 0.0)) + float(t3_wizard_totals.get("box34_foreign_tax_paid", 0.0)),
        "foreign_income_total": foreign_income,
        "foreign_tax_paid_total": foreign_tax_paid,
        "t2209_non_business_tax_paid": t2209_non_business_tax_paid,
        "t2209_net_foreign_non_business_income": t2209_net_foreign_non_business_income,
        "t2209_net_income_override": t2209_net_income_override,
        "income_tax_withheld_manual": income_tax_withheld,
        "income_tax_withheld_total": income_tax_withheld_total,
        "cpp_withheld_total": cpp_withheld_total,
        "ei_withheld_total": ei_withheld_total,
        "t4a_tax_withheld_total": float(t4a_wizard_totals.get("box22_tax_withheld", 0.0)),
        "tuition_carryforward_available_total": tuition_carryforward_available_total,
        "tuition_carryforward_claim_requested": tuition_carryforward_claim_requested,
        "donation_carryforward_available_total": donation_carryforward_available_total,
        "donation_carryforward_claim_requested": donation_carryforward_claim_requested,
        "schedule9_regular_limit_preview": schedule9_regular_limit_preview,
        "schedule9_current_year_donations_claim_requested": schedule9_current_year_donations_claim_requested,
        "ecological_cultural_gifts": ecological_cultural_gifts,
        "net_capital_loss_carryforward": net_capital_loss_carryforward,
        "taxable_capital_gains": taxable_capital_gains,
        "estimated_total_income": estimated_total_income,
        "estimated_working_income": employment_income,
        "estimated_adjusted_net_income_for_cwb": estimated_adjusted_net_income_for_cwb,
        "estimated_spouse_adjusted_net_income_for_cwb": estimated_spouse_adjusted_net_income_for_cwb,
        "tax_year": tax_year,
        "province": province,
        "age": age,
        "ontario_seniors_public_transit_expenses": ontario_seniors_public_transit_expenses,
        "bc_renters_credit_eligible": float(bc_renters_credit_eligible),
        "bc_home_renovation_expenses": bc_home_renovation_expenses,
        "bc_home_renovation_eligible": float(bc_home_renovation_eligible),
        "sk_fertility_treatment_expenses": sk_fertility_treatment_expenses,
        "pe_volunteer_credit_eligible": float(pe_volunteer_credit_eligible),
        "t4_box24_total": t4_reference_box24_total,
        "t4_box26_total": t4_reference_box26_total,
        "estimator_ei_insurable_earnings": estimator_ei_insurable_earnings,
        "estimator_cpp_pensionable_earnings": estimator_cpp_pensionable_earnings,
        "cwb_basic_eligible": float(cwb_basic_eligible),
        "canada_workers_benefit_manual": canada_workers_benefit,
        "canada_workers_benefit_auto": auto_canada_workers_benefit_preview["credit"] + auto_cwb_disability_supplement_preview["credit"],
        "cwb_disability_supplement_eligible": float(cwb_disability_supplement_eligible),
        "spouse_cwb_disability_supplement_eligible": float(spouse_cwb_disability_supplement_eligible),
        "canada_training_credit_limit_available": canada_training_credit_limit_available,
        "canada_training_credit_manual": canada_training_credit,
        "medical_expense_supplement_manual": medical_expense_supplement,
        "medical_expense_supplement_auto": auto_medical_expense_supplement_preview["credit"],
        "medical_claim_amount": estimated_medical_claim_amount,
        "cpp_overpayment_refund_auto": auto_payroll_overpayment_preview["cpp_overpayment"],
        "ei_overpayment_refund_auto": auto_payroll_overpayment_preview["ei_overpayment"],
        "manual_refundable_credits_total": refundable_credits_engine_total,
        "provincial_special_refundable_credits": (
            mb479_personal_tax_credit
            + mb479_homeowners_affordability_credit
            + mb479_renters_affordability_credit
            + mb479_seniors_school_rebate
            + mb479_primary_caregiver_credit
            + ns479_volunteer_credit
            + ns479_childrens_sports_arts_credit
            + nb_seniors_home_renovation_expenses * 0.10
            + nl479_other_refundable_credits
        ),
    }
)

wizard_spouse_claim_enabled = bool(st.session_state.get("spouse_claim_enabled", spouse_claim_enabled))
wizard_has_spouse_end_of_year = bool(st.session_state.get("has_spouse_end_of_year", has_spouse_end_of_year))
wizard_separated_in_year = bool(st.session_state.get("separated_in_year", separated_in_year))
wizard_support_payments_to_spouse = bool(st.session_state.get("support_payments_to_spouse", support_payments_to_spouse))
wizard_spouse_infirm = bool(st.session_state.get("spouse_infirm", spouse_infirm))
wizard_spouse_net_income = float(st.session_state.get("spouse_net_income", spouse_net_income))
wizard_spouse_amount_claim = float(st.session_state.get("spouse_amount_claim", spouse_amount_claim))
wizard_eligible_dependant_claim_enabled = bool(st.session_state.get("eligible_dependant_claim_enabled", eligible_dependant_claim_enabled))
wizard_eligible_dependant_net_income = float(st.session_state.get("eligible_dependant_net_income", eligible_dependant_net_income))
wizard_eligible_dependant_claim = float(st.session_state.get("eligible_dependant_claim", eligible_dependant_claim))
wizard_cwb_basic_eligible = bool(st.session_state.get("cwb_basic_eligible", cwb_basic_eligible))
wizard_cwb_disability_supplement_eligible = bool(st.session_state.get("cwb_disability_supplement_eligible", cwb_disability_supplement_eligible))
wizard_spouse_cwb_disability_supplement_eligible = bool(
    st.session_state.get("spouse_cwb_disability_supplement_eligible", spouse_cwb_disability_supplement_eligible)
)
wizard_canada_workers_benefit = float(st.session_state.get("canada_workers_benefit", canada_workers_benefit))
wizard_spouse_amount_preview = 0.0
if (
    wizard_spouse_claim_enabled
    and wizard_has_spouse_end_of_year
    and not wizard_separated_in_year
    and not wizard_support_payments_to_spouse
):
    wizard_spouse_amount_preview = calculate_spouse_amount(
        calculate_federal_bpa(estimated_net_income, t4_params),
        wizard_spouse_net_income,
        wizard_spouse_infirm,
    )
wizard_cwb_preview_credit = 0.0
if wizard_cwb_basic_eligible:
    wizard_cwb_preview = calculate_canada_workers_benefit(
        tax_year=tax_year,
        working_income=employment_income,
        adjusted_net_income=estimated_adjusted_net_income_for_cwb,
        spouse_adjusted_net_income=estimated_spouse_adjusted_net_income_for_cwb,
        has_spouse=wizard_has_spouse_end_of_year,
        has_eligible_dependant=(
            (wizard_eligible_dependant_claim_enabled or additional_dependant_count > 0)
            and not wizard_has_spouse_end_of_year
        ),
    )
    wizard_cwb_disability_preview = calculate_cwb_disability_supplement(
        tax_year=tax_year,
        adjusted_net_income=estimated_adjusted_net_income_for_cwb,
        spouse_adjusted_net_income=estimated_spouse_adjusted_net_income_for_cwb,
        has_spouse=wizard_has_spouse_end_of_year,
        is_disabled=wizard_cwb_disability_supplement_eligible,
        spouse_is_disabled=wizard_spouse_cwb_disability_supplement_eligible,
    )
    wizard_cwb_preview_credit = wizard_cwb_preview["credit"] + wizard_cwb_disability_preview["credit"]

if current_step == 7:
    st.markdown("### 7) Summary & Pre-Calculation Diagnostics")
    st.caption("This is the final pre-calculation gate. Review any flagged items, then calculate when the file looks ready.")
    high_risk_count = sum(1 for severity, _, _ in diagnostics if severity == "High-Risk")
    warning_count = sum(1 for severity, _, _ in diagnostics if severity == "Warning")
    info_count = sum(1 for severity, _, _ in diagnostics if severity == "Info")
    with st.container(border=True):
        st.markdown("##### Final Checkpoint")
        st.caption("Confirm the main inputs below, then check whether any diagnostic items still need attention.")
        st.markdown("###### Input Snapshot")
        current_input_summary = [
            ("Employment Income", employment_income),
            ("Investment / Other Income", other_income + interest_income + taxable_capital_gains + t5_eligible_dividends_taxable + t5_non_eligible_dividends_taxable + t3_eligible_dividends_taxable + t3_non_eligible_dividends_taxable),
            ("Deductions Entered", estimated_total_deductions),
            ("Tax Withheld", income_tax_withheld_total),
        ]
        render_metric_row(current_input_summary, 4)
        st.divider()
        st.markdown("###### Diagnostic Status")
        render_metric_row(
            [
                ("High-Risk", float(high_risk_count)),
                ("Warnings", float(warning_count)),
                ("Info", float(info_count)),
            ],
            3,
            formatter=format_plain_number,
        )
        if diagnostics:
            if high_risk_count > 0:
                st.warning("High-risk items are still showing. It is worth checking those before you calculate.")
            elif warning_count > 0:
                st.info("Only review-level items are showing. You can still calculate now, then come back if needed.")
            else:
                st.success("No major pre-calculation issues are standing out. You can calculate the return when ready.")
            st.markdown("###### Diagnostic Details")
            render_diagnostics_panel(diagnostics, formatter=format_plain_number, show_counts=False)
        else:
            st.success("No major pre-calculation issues are standing out. You can calculate the return when ready.")
            st.markdown("###### Diagnostic Details")
            st.caption("No obvious duplication or consistency issues were detected from the current inputs.")

    action_col1, action_col2, action_col3 = st.columns([1.2, 0.7, 4.1])
    with action_col1:
        calculate_clicked = st.button("Calculate Return", type="primary", use_container_width=True)
    with action_col2:
        reset_clicked = st.button("Reset", use_container_width=True)
    back_col1, back_col2 = st.columns([1, 1])
    with back_col1:
        if st.button("Back", key="back_step_7", use_container_width=True):
            st.session_state["current_flow_step"] = 6
            st.rerun()

if reset_clicked:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

calculation_inputs = {
            "tax_year": tax_year,
            "province": province,
            "age": age,
            "employment_income": employment_income,
            "pension_income": pension_income,
            "rrsp_rrif_income": rrsp_rrif_income_manual,
            "other_income": other_income,
            "net_rental_income": t776_net_rental_income,
            "manual_net_rental_income": manual_net_rental_income,
            "t776_gross_rents": t776_gross_rents,
            "t776_advertising": t776_advertising,
            "t776_insurance": t776_insurance,
            "t776_interest_bank_charges": t776_interest_bank_charges,
            "t776_property_taxes": t776_property_taxes,
            "t776_utilities": t776_utilities,
            "t776_repairs_maintenance": t776_repairs_maintenance,
            "t776_management_admin": t776_management_admin,
            "t776_travel": t776_travel,
            "t776_office_expenses": t776_office_expenses,
            "t776_other_expenses": t776_other_expenses,
            "t776_total_expenses_before_cca": t776_total_expenses_before_cca,
            "t776_cca": t776_cca,
            "t776_net_rental_income_before_manual": t776_net_rental_income,
            "taxable_capital_gains": schedule3_taxable_capital_gains,
            "manual_taxable_capital_gains": manual_taxable_capital_gains,
            "schedule3_proceeds_total": schedule3_proceeds_total,
            "schedule3_acb_total": schedule3_acb_total,
            "schedule3_outlays_total": schedule3_outlays_total,
            "schedule3_gross_capital_gains": schedule3_gross_capital_gains,
            "schedule3_gross_capital_losses": schedule3_gross_capital_losses,
            "schedule3_net_capital_gain_or_loss": schedule3_net_capital_gain_or_loss,
            "schedule3_taxable_capital_gains_before_manual": schedule3_taxable_capital_gains,
            "schedule3_allowable_capital_loss": schedule3_allowable_capital_loss,
            "schedule3_t3_box21_amount": t3_box21_capital_amount,
            "schedule3_t4ps_box34_amount": t4ps_box34_capital_amount,
            "interest_income": interest_income,
            "eligible_dividends": eligible_dividends,
            "non_eligible_dividends": non_eligible_dividends,
            "t5_eligible_dividends_taxable": t5_eligible_dividends_taxable,
            "t5_non_eligible_dividends_taxable": t5_non_eligible_dividends_taxable,
            "t5_federal_dividend_credit": t5_federal_dividend_credit,
            "t3_eligible_dividends_taxable": t3_eligible_dividends_taxable,
            "t3_non_eligible_dividends_taxable": t3_non_eligible_dividends_taxable,
            "t3_federal_dividend_credit": t3_federal_dividend_credit,
            "rrsp_deduction": rrsp_deduction,
            "fhsa_deduction": fhsa_deduction,
            "rpp_contribution": rpp_contribution,
            "union_dues": union_dues,
            "child_care_expenses": child_care_expenses,
            "moving_expenses": moving_expenses,
            "support_payments_deduction": support_payments_deduction,
            "carrying_charges": carrying_charges,
            "other_employment_expenses": other_employment_expenses,
            "other_deductions": other_deductions,
            "net_capital_loss_carryforward": net_capital_loss_carryforward,
            "other_loss_carryforward": other_loss_carryforward,
            "spouse_amount_claim": wizard_spouse_amount_claim,
            "spouse_net_income": wizard_spouse_net_income,
            "spouse_claim_enabled": wizard_spouse_claim_enabled,
            "spouse_infirm": wizard_spouse_infirm,
            "has_spouse_end_of_year": wizard_has_spouse_end_of_year,
            "separated_in_year": wizard_separated_in_year,
            "support_payments_to_spouse": wizard_support_payments_to_spouse,
            "eligible_dependant_claim": wizard_eligible_dependant_claim,
            "eligible_dependant_net_income": wizard_eligible_dependant_net_income,
            "eligible_dependant_claim_enabled": wizard_eligible_dependant_claim_enabled,
            "eligible_dependant_infirm": eligible_dependant_infirm,
            "dependant_relationship": dependant_relationship,
            "dependant_category": dependant_category,
            "dependant_lived_with_you": dependant_lived_with_you,
            "paid_child_support_for_dependant": paid_child_support_for_dependant,
            "shared_custody_claim_agreement": shared_custody_claim_agreement,
            "another_household_member_claims_dependant": another_household_member_claims_dependant,
            "another_household_member_claims_caregiver": another_household_member_claims_caregiver,
            "another_household_member_claims_disability_transfer": another_household_member_claims_disability_transfer,
            "medical_dependant_claim_shared": medical_dependant_claim_shared,
            "spouse_disability_transfer_available": spouse_disability_transfer_available,
            "spouse_disability_transfer_available_amount": spouse_disability_transfer_available_amount,
            "dependant_disability_transfer_available": dependant_disability_transfer_available,
            "dependant_disability_transfer_available_amount": dependant_disability_transfer_available_amount,
            "additional_dependant_count": float(additional_dependant_count),
            "additional_dependant_caregiver_claim_total": additional_dependant_caregiver_claim_total,
            "additional_dependant_disability_transfer_available_total": additional_dependant_disability_transfer_available_total,
            "additional_dependant_medical_claim_total": additional_dependant_medical_claim_total,
            "caregiver_claim_target": caregiver_claim_target,
            "disability_amount_claim": disability_amount_claim,
            "age_amount_claim": age_amount_claim,
            "tuition_amount_claim": tuition_amount_claim,
            "tuition_transfer_from_spouse": tuition_transfer_from_spouse,
            "schedule11_current_year_tuition_available": schedule11_current_year_tuition_available,
            "schedule11_carryforward_available": tuition_carryforward_available_total,
            "schedule11_current_year_claim_requested": schedule11_current_year_claim_requested,
            "schedule11_carryforward_claim_requested": tuition_carryforward_claim_requested,
            "schedule11_transfer_from_spouse": tuition_transfer_from_spouse,
            "student_loan_interest": student_loan_interest,
            "medical_expenses_eligible": medical_expenses_eligible,
            "medical_expenses_paid": medical_expenses_paid,
            "charitable_donations": charitable_donations,
            "additional_federal_credits": additional_federal_credits,
            "additional_provincial_credit_amount": additional_provincial_credit_amount + provincial_credit_lines_total,
            "provincial_caregiver_claim_amount": ontario_caregiver_amount,
            "ontario_caregiver_amount": ontario_caregiver_amount,
            "ontario_student_loan_interest": ontario_student_loan_interest,
            "ontario_tuition_transfer": ontario_tuition_transfer,
            "disability_transfer_source": disability_transfer_source,
            "ontario_disability_transfer": ontario_disability_transfer,
            "ontario_adoption_expenses": ontario_adoption_expenses,
            "ontario_medical_dependants": ontario_medical_dependants,
            "provincial_dependent_children_count": ontario_dependent_children_count,
            "ontario_dependent_children_count": ontario_dependent_children_count,
            "ontario_dependant_impairment_count": ontario_dependant_impairment_count,
            "foreign_income": foreign_income,
            "foreign_tax_paid": foreign_tax_paid,
            "t2209_non_business_tax_paid": t2209_non_business_tax_paid,
            "t2209_net_foreign_non_business_income": t2209_net_foreign_non_business_income,
            "t2209_net_income_override": t2209_net_income_override,
            "t2209_basic_federal_tax_override": t2209_basic_federal_tax_override,
            "t2036_provincial_tax_otherwise_payable_override": t2036_provincial_tax_otherwise_payable_override,
            "provincial_dividend_tax_credit_manual": ontario_dividend_tax_credit_manual,
            "donations_eligible_total": donations_eligible_total + donation_carryforward_claim_total,
            "schedule9_current_year_donations_available": schedule9_current_year_donations_available,
            "schedule9_current_year_donations_claim_requested": schedule9_current_year_donations_claim_requested,
            "schedule9_carryforward_available": donation_carryforward_available_total,
            "schedule9_carryforward_claim_requested": donation_carryforward_claim_requested,
            "ecological_cultural_gifts": ecological_cultural_gifts,
            "ecological_gifts_pre2016": ecological_gifts_pre2016,
            "income_tax_withheld": income_tax_withheld_total,
            "cpp_withheld_total": cpp_withheld_total,
            "ei_withheld_total": ei_withheld_total,
            "installments_paid": installments_paid,
            "other_payments": other_payments,
            "canada_workers_benefit": wizard_canada_workers_benefit,
            "cwb_basic_eligible": wizard_cwb_basic_eligible,
            "cwb_disability_supplement_eligible": wizard_cwb_disability_supplement_eligible,
            "spouse_cwb_disability_supplement_eligible": wizard_spouse_cwb_disability_supplement_eligible,
            "canada_training_credit_limit_available": canada_training_credit_limit_available,
            "canada_training_credit": canada_training_credit,
            "medical_expense_supplement": medical_expense_supplement,
            "other_federal_refundable_credits": other_federal_refundable_credits,
            "manual_provincial_refundable_credits": manual_provincial_refundable_credits,
            "other_manual_refundable_credits": refundable_credits,
            "ontario_fertility_treatment_expenses": ontario_fertility_treatment_expenses,
            "ontario_seniors_public_transit_expenses": ontario_seniors_public_transit_expenses,
            "bc_renters_credit_eligible": bc_renters_credit_eligible,
            "bc_home_renovation_expenses": bc_home_renovation_expenses,
            "bc_home_renovation_eligible": bc_home_renovation_eligible,
            "sk_fertility_treatment_expenses": sk_fertility_treatment_expenses,
            "pe_volunteer_credit_eligible": pe_volunteer_credit_eligible,
            "mb479_personal_tax_credit": mb479_personal_tax_credit,
            "mb479_homeowners_affordability_credit": mb479_homeowners_affordability_credit,
            "mb479_renters_affordability_credit": mb479_renters_affordability_credit,
            "mb479_seniors_school_rebate": mb479_seniors_school_rebate,
            "mb479_primary_caregiver_credit": mb479_primary_caregiver_credit,
            "mb479_fertility_treatment_expenses": mb479_fertility_treatment_expenses,
            "ns479_volunteer_credit": ns479_volunteer_credit,
            "ns479_childrens_sports_arts_credit": ns479_childrens_sports_arts_credit,
            "nb_political_contribution_credit": nb_political_contribution_credit,
            "nb_small_business_investor_credit": nb_small_business_investor_credit,
            "nb_lsvcc_credit": nb_lsvcc_credit,
            "nb_seniors_home_renovation_expenses": nb_seniors_home_renovation_expenses,
            "nl_political_contribution_credit": nl_political_contribution_credit,
            "nl_direct_equity_credit": nl_direct_equity_credit,
            "nl_resort_property_credit": nl_resort_property_credit,
            "nl_venture_capital_credit": nl_venture_capital_credit,
            "nl_unused_venture_capital_credit": nl_unused_venture_capital_credit,
            "nl479_other_refundable_credits": nl479_other_refundable_credits,
            "t4ps_box41_epsp_contributions": t4ps_box41_epsp_contributions,
        }
current_input_signature = build_input_signature(calculation_inputs)

stored_input_signature = st.session_state.get("tax_result_input_signature")
if (
    "tax_result" in st.session_state
    and stored_input_signature is not None
    and stored_input_signature != current_input_signature
    and not calculate_clicked
):
    del st.session_state["tax_result"]
    del st.session_state["tax_result_input_signature"]
    st.rerun()

if calculate_clicked:
    result = calculate_personal_tax_return(calculation_inputs)
    postcalc_diagnostics = collect_postcalc_diagnostics(result)
    st.session_state["tax_result"] = result
    st.session_state["tax_result_input_signature"] = current_input_signature

if "tax_result" in st.session_state and st.session_state.get("tax_result_input_signature") == current_input_signature:
    result = st.session_state["tax_result"]
    postcalc_diagnostics = collect_postcalc_diagnostics(result)
    if current_step == 7:
        pass
    st.subheader("Results")
    provincial_form_code = PROVINCIAL_FORM_CODES.get(province, "428")
    tab_names = ["Summary", "Return Details", "Advanced Checks", "Foreign Tax Credit", provincial_form_code, "Rental Details", "Capital Gains", "Tuition", "Donations", "Scope / Limits"]
    special_tab_name = None
    if province == "MB":
        special_tab_name = "MB428-A / MB479"
    elif province == "NS":
        special_tab_name = "NS479"
    elif province == "ON":
        special_tab_name = "ON479"
    elif province == "BC":
        special_tab_name = "BC479 / BC(S12)"
    elif province == "SK":
        special_tab_name = "SK479"
    elif province == "NB":
        special_tab_name = "NB428 / NB(S12)"
    elif province == "NL":
        special_tab_name = "NL428 / NL479"
    elif province == "PE":
        special_tab_name = "PE Low-Income / Volunteer"
    if special_tab_name:
        tab_names.append(special_tab_name)
    tabs = st.tabs(tab_names)
    client_summary_tab = tabs[0]
    return_tab = tabs[1]
    reconciliation_tab = tabs[2]
    t2209_tab = tabs[3]
    provincial_tab = tabs[4]
    t776_tab = tabs[5]
    s3_tab = tabs[6]
    s11_tab = tabs[7]
    s9_tab = tabs[8]
    scope_tab = tabs[9]
    special_tab = tabs[10] if special_tab_name else None

    with client_summary_tab:
        st.markdown("#### Summary")
        client_drivers_df = build_client_key_drivers_df(
            result,
            province_name,
            build_label_amount_df=build_label_amount_df,
        )
        readiness_df = build_filing_readiness_df(
            result=result,
            diagnostics=diagnostics,
            postcalc_diagnostics=postcalc_diagnostics,
            province=province,
            province_name=province_name,
        )
        summary_wizard_signal_totals = {
            "t3": float(t3_wizard_totals.sum()) if hasattr(t3_wizard_totals, "sum") else 0.0,
            "t5": float(t5_wizard_totals.sum()) if hasattr(t5_wizard_totals, "sum") else 0.0,
        }
        summary_raw_input_signals = {
            "tax_year": tax_year,
            "province": province,
            "age": age,
            "spouse_claim_enabled": wizard_spouse_claim_enabled,
            "has_spouse_end_of_year": wizard_has_spouse_end_of_year,
            "separated_in_year": wizard_separated_in_year,
            "support_payments_to_spouse": wizard_support_payments_to_spouse,
            "spouse_infirm": wizard_spouse_infirm,
            "eligible_dependant_claim_enabled": wizard_eligible_dependant_claim_enabled,
            "dependant_lived_with_you": dependant_lived_with_you,
            "dependant_relationship": dependant_relationship,
            "dependant_category": dependant_category,
            "paid_child_support_for_dependant": paid_child_support_for_dependant,
            "shared_custody_claim_agreement": shared_custody_claim_agreement,
            "another_household_member_claims_dependant": another_household_member_claims_dependant,
            "cwb_basic_eligible": wizard_cwb_basic_eligible,
            "cwb_disability_supplement_eligible": wizard_cwb_disability_supplement_eligible,
            "spouse_cwb_disability_supplement_eligible": wizard_spouse_cwb_disability_supplement_eligible,
            "medical_expenses_paid": st.session_state.get("medical_expenses_paid", 0.0),
            "charitable_donations": st.session_state.get("charitable_donations", 0.0),
            "donations_eligible_total": st.session_state.get("donations_eligible_total", 0.0),
            "moving_expenses": st.session_state.get("moving_expenses", 0.0),
            "child_care_expenses": st.session_state.get("child_care_expenses", 0.0),
            "other_employment_expenses": st.session_state.get("other_employment_expenses", 0.0),
            "rrsp_deduction": st.session_state.get("rrsp_deduction", 0.0),
            "fhsa_deduction": st.session_state.get("fhsa_deduction", 0.0),
            "support_payments_deduction": st.session_state.get("support_payments_deduction", 0.0),
            "foreign_income": st.session_state.get("foreign_income", 0.0),
            "foreign_tax_paid": st.session_state.get("foreign_tax_paid", 0.0),
            "interest_income": st.session_state.get("interest_income", 0.0),
            "eligible_dividends": st.session_state.get("eligible_dividends", 0.0),
            "non_eligible_dividends": st.session_state.get("non_eligible_dividends", 0.0),
            "student_loan_interest": st.session_state.get("student_loan_interest", 0.0),
            "tuition_amount_claim": st.session_state.get("tuition_amount_claim", 0.0),
            "schedule11_current_year_tuition_available": result.get("schedule11_current_year_tuition_available", 0.0),
            "schedule11_carryforward_available": result.get("schedule11_carryforward_available", 0.0),
            "canada_training_credit_limit_available": st.session_state.get("canada_training_credit_limit_available", 0.0),
            "bc_renters_credit_eligible": st.session_state.get("bc_renters_credit_eligible", False),
            "t776_property_taxes": st.session_state.get("t776_property_taxes", 0.0),
            "canada_workers_benefit": wizard_canada_workers_benefit,
            "canada_training_credit": st.session_state.get("canada_training_credit", 0.0),
            "medical_expense_supplement": st.session_state.get("medical_expense_supplement", 0.0),
            "other_federal_refundable_credits": st.session_state.get("other_federal_refundable_credits", 0.0),
            "manual_provincial_refundable_credits": st.session_state.get("manual_provincial_refundable_credits", 0.0),
            "refundable_credits": st.session_state.get("refundable_credits", 0.0),
            "spouse_amount_claim": wizard_spouse_amount_claim,
            "eligible_dependant_claim": wizard_eligible_dependant_claim,
            "spouse_net_income": wizard_spouse_net_income,
            "income_tax_withheld": st.session_state.get("income_tax_withheld", 0.0),
            "cpp_withheld": st.session_state.get("cpp_withheld", 0.0),
            "ei_withheld": st.session_state.get("ei_withheld", 0.0),
            "installments_paid": st.session_state.get("installments_paid", 0.0),
            "other_payments": st.session_state.get("other_payments", 0.0),
            "t2209_non_business_tax_paid": st.session_state.get("t2209_non_business_tax_paid", 0.0),
            "t2209_net_foreign_non_business_income": st.session_state.get("t2209_net_foreign_non_business_income", 0.0),
            "t2209_net_income_override": st.session_state.get("t2209_net_income_override", 0.0),
            "t2209_basic_federal_tax_override": st.session_state.get("t2209_basic_federal_tax_override", 0.0),
            "t2036_provincial_tax_otherwise_payable_override": st.session_state.get("t2036_provincial_tax_otherwise_payable_override", 0.0),
        }
        summary_screening = build_screening_inputs(
            province=province,
            province_name=province_name,
            session_state=st.session_state,
            wizard_totals=summary_wizard_signal_totals,
            raw_inputs=summary_raw_input_signals,
        )
        summary_eligibility_decision = build_eligibility_decision(
            tax_year=tax_year,
            province=province,
            age=float(age or 0.0),
            raw_inputs=summary_raw_input_signals,
            result=result,
        )
        summary_progress = build_section_progress(
            session_state=st.session_state,
            wizard_totals=summary_wizard_signal_totals,
            raw_inputs=summary_raw_input_signals,
            result=result,
            eligibility_decision=summary_eligibility_decision,
        )
        summary_guidance_items = build_eligibility_guidance(summary_screening, summary_eligibility_decision, summary_progress)
        summary_completion_flags = build_completion_flags(
            screening=summary_screening,
            progress=summary_progress,
            wizard_totals=summary_wizard_signal_totals,
            raw_inputs=summary_raw_input_signals,
            result=result,
            readiness_df=readiness_df,
            eligibility_decision=summary_eligibility_decision,
        )
        summary_suggestions = build_suggestions(
            screening=summary_screening,
            guidance_items=summary_guidance_items,
            progress=summary_progress,
            completion_flags=summary_completion_flags,
        )
        quick_review_items, top_warning_items, top_override_items = build_results_quick_notes(
            result=result,
            readiness_df=readiness_df,
            diagnostics=diagnostics,
            postcalc_diagnostics=postcalc_diagnostics,
            reconciliation_df=None,
            assumptions_df=None,
            format_currency=format_currency,
        )
        render_answer_summary_sheet(
            result=result,
            province_name=province_name,
            readiness_df=readiness_df,
            suggestions=summary_suggestions,
            calculation_inputs=calculation_inputs,
        )
        with st.expander("Client Review Details", expanded=False):
            st.markdown("#### Plain-Language Numbers")
            st.dataframe(
                build_client_summary_df(
                    result,
                    province_name,
                    format_currency=format_currency,
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("#### Main Reasons The Result Changed")
            if client_drivers_df.empty:
                st.caption("No major deductions, credits, or payment drivers are standing out yet.")
            else:
                st.dataframe(client_drivers_df, use_container_width=True, hide_index=True)
            st.markdown("#### Before Filing Checklist")
            render_filing_readiness_panel(readiness_df)
        printable_html = build_printable_client_summary_html(
            result,
            province_name,
            readiness_df,
            client_drivers_df,
            format_currency=format_currency,
            include_cta=False,
        )
        printable_pdf = build_printable_client_summary_pdf(
            result,
            province_name,
            readiness_df,
            client_drivers_df,
            format_currency=format_currency,
            logo_path=Path(__file__).resolve().parent / "contexta_logo.png",
        )
        with st.expander("Printable Shareable Summary", expanded=False):
            st.markdown(printable_html, unsafe_allow_html=True)
            st.download_button(
                "Download Shareable Summary (PDF)",
                data=printable_pdf,
                file_name=f"{province_name.lower().replace(' ', '-')}-tax-estimate-summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        st.caption("Simpler summary for sharing. Use the worksheet tabs only if you want line detail.")
        st.caption("If you want a second review of slips, support, or filing readiness, reach out: info@contexta.biz")

    with return_tab:
        st.caption("Worksheet view. Start with the overview and open the line details only if needed.")

        overview_col1, overview_col2 = st.columns(2)
        with overview_col1:
            st.markdown("#### Return Overview")
            summary_df = build_summary_df(result)
            st.dataframe(
                summary_df.assign(Amount=summary_df["Amount"].map(format_currency)),
                use_container_width=True,
                hide_index=True,
            )
        with overview_col2:
            st.markdown("#### Credits And Deductions Used")
            credit_rows = build_currency_df(
                [
                    {"Item": "Total Deductions", "Amount": result["total_deductions"]},
                    {"Item": "RRSP / RRIF Income", "Amount": result.get("line_rrsp_rrif_income", 0.0)},
                    {"Item": "Other Employment Expenses", "Amount": result.get("line_other_employment_expenses", 0.0)},
                    {"Item": "Federal Non-Refundable Credits", "Amount": result["federal_non_refundable_credits"]},
                    {"Item": f"{province_name} Non-Refundable Credits", "Amount": result["provincial_non_refundable_credits"]},
                    {"Item": "Tax Payments / Withholding", "Amount": result["income_tax_withheld"] + result["installments_paid"] + result["other_payments"]},
                    {"Item": "CPP/EI Overpayment Refunds", "Amount": result.get("payroll_overpayment_refund_total", 0.0)},
                    {"Item": "Refundable Credits", "Amount": result["refundable_credits"]},
                ],
                ["Amount"],
            )
            st.dataframe(credit_rows, use_container_width=True, hide_index=True)

        with st.expander("Line Details And Forms Used", expanded=False):
            line_df = line_summary_df(result, province_name)
            line_df["Amount"] = line_df["Amount"].map(format_currency)
            st.markdown("#### Line-By-Line Return Summary")
            st.dataframe(line_df, use_container_width=True, hide_index=True)
            package_df = build_return_package_df(
                result,
                province_name,
                format_currency=format_currency,
            )
            st.markdown("#### Included Forms And Schedules")
            st.dataframe(package_df, use_container_width=True, hide_index=True)
        with st.expander("Federal Net Tax Build-Up", expanded=False):
            federal_build_up_df = build_federal_net_tax_build_up_df(result)
            federal_build_up_df["Amount"] = federal_build_up_df["Amount"].map(format_currency)
            st.dataframe(federal_build_up_df, use_container_width=True, hide_index=True)

    with reconciliation_tab:
        st.markdown("#### Input Checks")
        st.caption("Most users can skip this tab. Open it only for a deeper audit trail.")
        if top_warning_items or top_override_items:
            with st.container(border=True):
                st.markdown("##### Why You Might Open This Tab")
                if top_warning_items:
                    st.markdown("\n".join(f"- {item}" for item in top_warning_items[:3]))
                if top_override_items:
                    st.markdown("\n".join(f"- {item}" for item in top_override_items[:3]))
        else:
            st.info("Nothing urgent is standing out from the current inputs. You only need this tab if you want a deeper audit trail.")

        with st.expander("Open Advanced Input Checks", expanded=False):
            reconciliation_df = build_slip_reconciliation_df(
                result=result,
                t4_wizard_totals=t4_wizard_totals,
                t4a_wizard_totals=t4a_wizard_totals,
                t5_wizard_totals=t5_wizard_totals,
                t3_wizard_totals=t3_wizard_totals,
                t4ps_wizard_totals=t4ps_wizard_totals,
                t2202_wizard_totals=t2202_wizard_totals,
                employment_income_manual=employment_income_manual,
                pension_income_manual=pension_income_manual,
                other_income_manual=other_income_manual,
                interest_income_manual=interest_income_manual,
                tuition_override=tuition_amount_claim,
                format_currency=format_currency,
            )
            render_reconciliation_panel(reconciliation_df)
            st.caption("This compares slip totals, manual inputs, and final return amounts.")

            st.markdown("#### Assumptions and Overrides Summary")
            assumptions_df = build_assumptions_overrides_df(
                result=result,
                province_name=province_name,
                tuition_claim_override=tuition_amount_claim,
                t2209_net_income_override=t2209_net_income_override,
                t2209_basic_federal_tax_override=t2209_basic_federal_tax_override,
                t2036_provincial_tax_otherwise_payable_override=t2036_provincial_tax_otherwise_payable_override,
                format_currency=format_currency,
            )
            render_assumptions_overrides_panel(assumptions_df)
            st.caption("This shows overrides, estimates, and cap/allocation rules.")

            st.markdown("#### Missing-Support Checklist")
            missing_support_df = build_missing_support_df(result, province, province_name)
            st.dataframe(missing_support_df, use_container_width=True, hide_index=True)
            st.caption("This lists support worth reviewing before filing.")

            st.markdown("#### Filing-Readiness Detail")
            render_filing_readiness_panel(readiness_df)
            st.caption("`Ready` means support looks complete. `Review` or `Missing` still need attention.")

            report_pack_pdf = build_report_pack_pdf(
                result=result,
                province=province,
                province_name=province_name,
                readiness_df=readiness_df,
                reconciliation_df=reconciliation_df,
                assumptions_df=assumptions_df,
                missing_support_df=missing_support_df,
            )
            st.download_button(
                "Download Report Pack (PDF)",
                data=report_pack_pdf,
                file_name=f"{province_name.lower().replace(' ', '-')}-tax-estimate-report-pack.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with t2209_tab:
        st.markdown("#### Foreign Tax Credit Worksheet")
        st.caption("Most users only need this if they are checking foreign tax credits in detail.")
        t2209_rows = build_currency_df(
            [
                {"Group": "Source Totals", "Line": "SRC-1", "Description": "Foreign non-business income used", "Amount": result["t2209_net_foreign_non_business_income"]},
                {"Group": "Source Totals", "Line": "SRC-2", "Description": "Foreign tax paid used", "Amount": result["t2209_non_business_tax_paid"]},
                {"Group": "T2209 Federal", "Line": "1", "Description": "Non-business income tax paid", "Amount": result["t2209_non_business_tax_paid"]},
                {"Group": "T2209 Federal", "Line": "2", "Description": "Net foreign non-business income", "Amount": result["t2209_net_foreign_non_business_income"]},
                {"Group": "T2209 Federal", "Line": "3", "Description": "Net income used", "Amount": result["t2209_net_income"]},
                {"Group": "T2209 Federal", "Line": "3A", "Description": "Foreign income ratio", "Amount": result["t2209_foreign_income_ratio"]},
                {"Group": "T2209 Federal", "Line": "4", "Description": "Basic federal tax used", "Amount": result["t2209_basic_federal_tax_used"]},
                {"Group": "T2209 Federal", "Line": "5", "Description": "Federal proportional limit before 15% cap", "Amount": result["t2209_limit_before_property_cap"]},
                {"Group": "T2209 Federal", "Line": "6", "Description": "Foreign property 15% cap", "Amount": result["foreign_property_limit"]},
                {"Group": "T2209 Federal", "Line": "40500", "Description": "Federal foreign tax credit claimed", "Amount": result["federal_foreign_tax_credit"]},
                {"Group": "T2036 Provincial", "Line": "1", "Description": "Residual foreign tax after federal credit", "Amount": result["t2036_line1"]},
                {"Group": "T2036 Provincial", "Line": "2", "Description": "Provincial tax otherwise payable", "Amount": result["provincial_tax_otherwise_payable"]},
                {"Group": "T2036 Provincial", "Line": "3", "Description": "Foreign income ratio", "Amount": result["t2036_foreign_income_ratio"]},
                {"Group": "T2036 Provincial", "Line": "4", "Description": "Provincial foreign tax credit limit", "Amount": result["t2036_limit"]},
                {"Group": "T2036 Provincial", "Line": "428-FTC", "Description": "Provincial foreign tax credit claimed", "Amount": result["provincial_foreign_tax_credit"]},
                {"Group": "T2036 Provincial", "Line": "Residual", "Description": "Residual foreign tax still unclaimed", "Amount": result["t2036_unused_foreign_tax"]},
            ],
            ["Amount"],
        )
        with st.expander("Detailed T2209 / T2036 Lines", expanded=False):
            st.dataframe(t2209_rows, use_container_width=True, hide_index=True)

    with provincial_tab:
        st.markdown(f"#### {province_name} Worksheet View")
        if province == "ON":
            with st.expander("ON428 Part C Lines 74-90", expanded=False):
                on428_part_c_df = build_on428_part_c_df(result)
                on428_part_c_df["Amount"] = on428_part_c_df["Amount"].map(format_currency)
                st.dataframe(on428_part_c_df, use_container_width=True, hide_index=True)
            with st.expander("ON428-A LIFT Worksheet", expanded=False):
                on428a_lift_df = build_on428a_lift_df(result)
                on428a_lift_df["Amount"] = on428a_lift_df["Amount"].map(format_currency)
                st.dataframe(on428a_lift_df, use_container_width=True, hide_index=True)
        provincial_rows = build_provincial_worksheet_df(result, province, province_name)
        provincial_rows["Amount"] = provincial_rows["Amount"].map(format_currency)
        with st.expander("Detailed Worksheet Lines", expanded=False):
            st.dataframe(provincial_rows, use_container_width=True, hide_index=True)

    with t776_tab:
        st.markdown("#### T776 Worksheet View")
        t776_rows = build_t776_df(result)
        t776_rows["Amount"] = t776_rows["Amount"].map(format_currency)
        with st.expander("Detailed T776 Lines", expanded=False):
            st.dataframe(t776_rows, use_container_width=True, hide_index=True)

    with s3_tab:
        st.markdown("#### Schedule 3 Worksheet View")
        s3_rows = build_schedule_3_df(result)
        s3_rows["Amount"] = s3_rows["Amount"].map(format_currency)
        with st.expander("Detailed Schedule 3 Lines", expanded=False):
            st.dataframe(s3_rows, use_container_width=True, hide_index=True)

    with s11_tab:
        st.markdown("#### Schedule 11 Worksheet View")
        st.caption("Training credit is applied first, then carryforward, then line 32300.")
        s11_rows = build_schedule_11_df(result)
        s11_rows["Amount"] = s11_rows["Amount"].map(format_currency)
        with st.expander("Detailed Schedule 11 Lines", expanded=False):
            st.dataframe(s11_rows, use_container_width=True, hide_index=True)

    with s9_tab:
        st.markdown("#### Schedule 9 Worksheet View")
        s9_rows = build_currency_df(
            [
                {"Line": "1A", "Description": "Current-year regular donations available", "Amount": result.get("schedule9_current_year_donations_available", 0.0)},
                {"Line": "1B", "Description": "Current-year regular donations claimed", "Amount": result.get("schedule9_current_year_donations_claim_used", 0.0)},
                {"Line": "1C", "Description": "Current-year regular donations unused", "Amount": result.get("schedule9_current_year_donations_unused", 0.0)},
                {"Line": "2A", "Description": "Donation carryforward available", "Amount": result.get("schedule9_carryforward_available", 0.0)},
                {"Line": "2B", "Description": "Donation carryforward requested", "Amount": result.get("schedule9_carryforward_claim_requested", 0.0)},
                {"Line": "2C", "Description": "Donation carryforward used", "Amount": result.get("schedule9_carryforward_claim_used", 0.0)},
                {"Line": "2D", "Description": "Donation carryforward unused", "Amount": result.get("schedule9_carryforward_unused", 0.0)},
                {"Line": "3", "Description": "Total regular donations claimed", "Amount": result.get("schedule9_total_regular_donations_claimed", 0.0)},
                {"Line": "4", "Description": "75% of net income regular-donation limit", "Amount": result.get("schedule9_regular_limit", 0.0)},
                {"Line": "5", "Description": "Cultural / ecological gifts claimed outside 75% limit", "Amount": result.get("schedule9_unlimited_gifts_claimed", 0.0)},
                {"Line": "13", "Description": "First $200 donations", "Amount": result["donation_first_200"]},
                {"Line": "14/16", "Description": "Amount above $200", "Amount": result["donation_amount_above_200"]},
                {"Line": "19/20", "Description": "High-rate portion", "Amount": result["donation_high_rate_portion"]},
                {"Line": "21/22", "Description": "Remaining 29% portion", "Amount": result.get("donation_remaining_29_portion", 0.0)},
                {"Line": "23", "Description": "Federal donation credit", "Amount": result["federal_donation_credit"]},
                {"Line": f"{provincial_form_code}-donation", "Description": f"{province_name} donation credit", "Amount": result.get("provincial_donation_credit", 0.0)},
            ],
            ["Amount"],
        )
        with st.expander("Detailed Schedule 9 Lines", expanded=False):
            st.dataframe(s9_rows, use_container_width=True, hide_index=True)

    with scope_tab:
        st.markdown("#### Supported Scope")
        with st.expander("Supported Scope", expanded=False):
            st.markdown(read_public_markdown_doc("PUBLIC_SUPPORTED_SCOPE.md"))
        with st.expander("Best-Fit And Manual Review Scenarios", expanded=False):
            st.markdown(read_public_markdown_doc("PUBLIC_BEST_FIT_AND_REVIEW_SCENARIOS.md"))
        with st.expander("Limitations And Boundaries", expanded=False):
            st.markdown(read_public_markdown_doc("PUBLIC_LIMITATIONS.md"))

    if special_tab is not None:
        with special_tab:
            st.markdown(f"#### {special_tab_name} Worksheet View")
            special_rows = build_special_schedule_df(result, province)
            if special_rows.empty:
                st.caption("No additional province-specific rows are available for this province yet.")
            else:
                special_rows["Amount"] = special_rows["Amount"].map(format_currency)
                st.dataframe(special_rows, use_container_width=True, hide_index=True)

    render_advanced_technical_details(
        result=result,
        province=province,
        province_name=province_name,
        tax_year=tax_year,
        t4_reference_box24_total=t4_reference_box24_total,
        t4_reference_box26_total=t4_reference_box26_total,
        t4_reference_box52_total=t4_reference_box52_total,
    )

st.markdown("---")
st.caption(
    "This estimator is much broader than the original employment-only calculator, but it is still not a substitute "
    "for CRA-certified filing software. Review slip amounts, carryforwards, and province-specific credits carefully."
)
