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
import sys
import os
sys.path.append(os.path.dirname(__file__))
from extraction.slip_parser import parse_pdf_slip
from guidance import (
    build_eligibility_guidance,
    build_completion_flags,
    build_screening_inputs,
    build_section_progress,
    build_suggestions,
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
)
from tax_config import AVAILABLE_TAX_YEARS, PROVINCES, TAX_CONFIGS
from tax_engine import calculate_personal_tax_return
from tax_engine.constants import FEDERAL_MEDICAL_THRESHOLDS
from tax_engine.credits import (
    calculate_canada_workers_benefit,
    calculate_cwb_disability_supplement,
    calculate_medical_claim,
    calculate_medical_expense_supplement,
    calculate_payroll_overpayment_refunds,
)
from tax_engine.utils import estimate_employee_cpp_ei

META_TITLE = "Tax Review & Optimization | Find Missed Deductions from Your T-Slips"
META_DESCRIPTION = (
    "Upload your T-slips and review your taxes in seconds. Check for missed deductions, credits, and benefits "
    "before filing your Ontario return."
)
OG_TITLE = "Review Your Ontario Taxes Before You File | Upload T-Slips Instantly"
OG_DESCRIPTION = (
    "Upload your T-slips and review your Ontario tax return in seconds. Check deductions, credits, and "
    "benefits before filing to avoid overpaying."
)
APP_URL = "https://advtax.contexta.biz/"
OG_IMAGE_URL = "https://advtax.contexta.biz/canadian-income-tax-estimator-og.jpg"
PROVINCIAL_FORM_CODES = {
    "ON": "ON428",
}


def build_input_signature(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
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
            "box24_total_months_part_time",
            "box25_total_months_full_time",
            "box26_total_eligible_tuition",
        ],
        "fields": [
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
        "should_fill": "Fill this if your school issued a T2202 for tuition. For the current Ontario MVP, focus on the total months and total eligible tuition boxes.",
        "tip": "Boxes 21-23 are hidden for now because the current calculator only uses the total-month and total-tuition figures.",
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
    return st.number_input(
        label,
        min_value=0.0,
        step=step,
        value=float(st.session_state.get(key, 0.0)),
        key=key,
        help=help_text,
    )


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


def build_productized_recommendation_cards(
    *,
    result: dict,
    has_spouse: bool,
    spouse_claim_enabled: bool,
    spouse_net_income: float,
    cwb_checked: bool,
    cwb_effective: bool,
    paid_rent_or_property_tax: bool,
    has_dependants: bool,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []

    def add_card(title: str, status: str, detail: str, next_step: str) -> None:
        cards.append(
            {
                "title": title,
                "status": status,
                "detail": detail,
                "next_step": next_step,
            }
        )

    spouse_amount_used = float(result.get("auto_spouse_amount", 0.0) or 0.0)
    if spouse_amount_used > 0:
        add_card(
            "Spouse Or Common-Law Partner Amount",
            "Included In Your Estimate",
            "This tax credit has already been included in your current estimate based on the spouse information entered.",
            "If any spouse details are wrong, go back to Quick Questions and update the household section.",
        )
    elif has_spouse and not spouse_claim_enabled:
        add_card(
            "Spouse Or Common-Law Partner Amount",
            "Needs More Information",
            "You indicated you had a spouse or common-law partner at year end, but the spouse amount check is not turned on.",
            "Go back to Quick Questions and turn on spouse amount eligibility if you want us to assess it.",
        )
    elif has_spouse and spouse_claim_enabled and spouse_net_income <= 0:
        add_card(
            "Spouse Or Common-Law Partner Amount",
            "Needs More Information",
            "We cannot confirm this credit yet because spouse net income is missing or still zero.",
            "Go back to Quick Questions and enter spouse net income to let the estimate assess this claim.",
        )
    elif has_spouse:
        add_card(
            "Spouse Or Common-Law Partner Amount",
            "Checked But Not Included",
            "The estimate reviewed this credit, but it is not currently adding any spouse amount to the result.",
            "Review the household details again only if your spouse information may have been entered incorrectly.",
        )

    cwb_used = float(result.get("canada_workers_benefit", 0.0) or 0.0)
    if cwb_used > 0:
        add_card(
            "Canada Workers Benefit (CWB)",
            "Included In Your Estimate",
            "Canada Workers Benefit has been included in your current estimate.",
            "If your working income or household details are wrong, go back to Quick Questions and review the CWB section.",
        )
    elif cwb_checked and not cwb_effective:
        add_card(
            "Canada Workers Benefit (CWB)",
            "Needs More Information",
            "You asked us to check CWB, but the current information does not let the estimate apply it yet.",
            "Review your household details and working-income-related inputs if you expected CWB to apply.",
        )
    elif not cwb_checked:
        add_card(
            "Canada Workers Benefit (CWB)",
            "Needs More Information",
            "CWB is not included because this check is currently turned off.",
            "Go back to Quick Questions and turn on the CWB check if you want the estimate to assess it.",
        )
    else:
        add_card(
            "Canada Workers Benefit (CWB)",
            "Checked But Not Included",
            "The estimate checked CWB, but it is not currently adding any amount to the result.",
            "Review only if you expected a CWB amount based on your work income and household situation.",
        )

    if paid_rent_or_property_tax:
        add_card(
            "Ontario Trillium Benefit (OTB)",
            "Not Included - Review Separately",
            "This estimate does not currently include Ontario Trillium Benefit in the refund or balance-owing result.",
            "Review OTB separately if you paid rent or property tax and may qualify.",
        )

    if has_dependants:
        add_card(
            "Canada Child Benefit (CCB)",
            "Not Included - Review Separately",
            "Canada Child Benefit is not calculated inside this estimate.",
            "Review CCB separately if you have children or dependants and want to confirm benefit eligibility.",
        )

    add_card(
        "GST/HST Credit",
        "Not Included - Review Separately",
        "GST/HST credit is not included in this estimate and does not change the refund shown here.",
        "File your return and review GST/HST credit eligibility separately if this benefit may matter to you.",
    )
    return cards


def render_productized_recommendation_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return
    status_style = {
        "Included In Your Estimate": ("#14532d", "#bbf7d0"),
        "Checked But Not Included": ("#1e3a8a", "#bfdbfe"),
        "Not Included - Review Separately": ("#78350f", "#fde68a"),
        "Needs More Information": ("#7f1d1d", "#fecaca"),
    }
    st.markdown("##### Recommended Next Checks")
    for section_title in [
        "Included In Your Estimate",
        "Checked But Not Included",
        "Not Included - Review Separately",
        "Needs More Information",
    ]:
        section_cards = [card for card in cards if card["status"] == section_title]
        if not section_cards:
            continue
        st.markdown(f"###### {section_title}")
        badge_bg, badge_fg = status_style.get(section_title, ("#374151", "#f3f4f6"))
        for card in section_cards:
            st.markdown(
                f"""
                <div style="border:1px solid #2a2f3a;border-radius:12px;padding:14px 16px;margin:10px 0;background:#111827;">
                    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px;">
                        <span style="background:{badge_bg};color:{badge_fg};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{card['status']}</span>
                        <span style="color:#f9fafb;font-weight:700;">{card['title']}</span>
                    </div>
                    <div style="color:#d1d5db;line-height:1.55;">
                        <strong style="color:#f3f4f6;">What this means:</strong> {card['detail']}<br>
                        <strong style="color:#f3f4f6;">Next step:</strong> {card['next_step']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def categorize_recommendation_item(item: "SuggestionItem") -> str:
    where = str(item.get("where", ""))
    item_id = str(item.get("id", ""))
    label = str(item.get("label", ""))
    if "Outside This Estimator" in where or item_id in {"gst_hst_credit", "ontario_trillium_benefit", "housing_benefits"}:
        return "Benefits To Review Separately"
    if item.get("priority") == "important" or label in {"Review this area", "Check this item"}:
        return "Items That Need A Second Look"
    return "Possible Tax Savings"


def render_client_recommendation_cards(suggestions: "list[SuggestionItem] | None" = None) -> None:
    if not suggestions:
        return
    priority_labels = {
        "important": ("Priority Check", "#7f1d1d", "#fecaca"),
        "review": ("Worth Reviewing", "#78350f", "#fde68a"),
        "info": ("Good To Know", "#1e3a8a", "#bfdbfe"),
        "maybe": ("Optional Check", "#374151", "#f3f4f6"),
    }
    grouped_items = {
        "Possible Tax Savings": [],
        "Benefits To Review Separately": [],
        "Items That Need A Second Look": [],
    }
    for item in suggestions:
        grouped_items[categorize_recommendation_item(item)].append(item)

    st.markdown("##### Recommended Next Checks")
    for section_title in ["Possible Tax Savings", "Benefits To Review Separately", "Items That Need A Second Look"]:
        section_items = grouped_items[section_title]
        if not section_items:
            continue
        st.markdown(f"###### {section_title}")
        for item in section_items:
            badge_label, badge_bg, badge_fg = priority_labels.get(
                item["priority"],
                ("Review", "#374151", "#f3f4f6"),
            )
            st.markdown(
                f"""
                <div style="border:1px solid #2a2f3a;border-radius:12px;padding:14px 16px;margin:10px 0;background:#111827;">
                    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px;">
                        <span style="background:{badge_bg};color:{badge_fg};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{badge_label}</span>
                        <span style="color:#f9fafb;font-weight:700;">{item['label']}</span>
                    </div>
                    <div style="color:#d1d5db;line-height:1.55;">
                        <strong style="color:#f3f4f6;">Why this may matter:</strong> {item['reason']}<br>
                        <strong style="color:#f3f4f6;">Where to review:</strong> {item['where']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_answer_summary_sheet(
    result: dict,
    province_name: str,
    readiness_df: pd.DataFrame,
    suggestions: "list[SuggestionItem] | None" = None,
    product_cards: list[dict[str, str]] | None = None,
) -> None:
    ready_count = int((readiness_df["Status"] == "Ready").sum()) if not readiness_df.empty else 0
    review_count = int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0
    missing_count = int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0

    if result.get("line_48400_refund", 0.0) > 0:
        st.success(
            f"Estimated refund: {format_currency(result['line_48400_refund'])}. "
            "Based on the slips, deductions, credits, and payments entered so far."
        )
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        st.warning(
            f"Estimated balance owing: {format_currency(result['line_48500_balance_owing'])}. "
            "Total tax payable is currently higher than withholding and other payments entered."
        )
    else:
        st.info(
            "Estimated result: near break-even. Small input changes could still move the file to either a refund or a balance owing."
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
    if product_cards:
        with st.container(border=True):
            render_productized_recommendation_cards(product_cards)
    elif suggestions:
        with st.container(border=True):
            render_client_recommendation_cards(suggestions)


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
                    {"Component": "Other Ontario Refundable Credits", "Amount": result.get("manual_provincial_refundable_credits", 0.0)},
                    {"Component": "Ontario Fertility Credit", "Amount": result.get("ontario_fertility_credit", 0.0)},
                    {"Component": "Ontario Seniors' Transit Credit", "Amount": result.get("ontario_seniors_transit_credit", 0.0)},
                    {"Component": "Other Manual Refundable Credits", "Amount": result.get("other_manual_refundable_credits", 0.0)},
                    {"Component": "Federal Refundable Credits Subtotal", "Amount": result.get("federal_refundable_credits", 0.0)},
                    {"Component": "Manual Refundable Credits Total", "Amount": result.get("manual_refundable_credits_total", 0.0)},
                    {"Component": "Ontario Special Refundable Credits", "Amount": result.get("provincial_special_refundable_credits", 0.0)},
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
            if province == "ON":
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
                - For 2025, the current MVP is tuned for Ontario-first review and Ontario worksheet coverage.
                - Ontario provincial dividend tax credits and key Ontario refundable credits are auto-estimated where supported by the current inputs.
                - Foreign tax credit now uses a clearer worksheet path: source foreign income and tax, T2209 federal ratio limit, 15% foreign property cap, T2036 residual provincial credit, and any remaining unclaimed foreign tax.
                - Tuition now follows a clearer Schedule 11-style flow with current-year T2202 amounts, carryforward availability, claimed amounts, transfer-in amounts, and unused balances shown separately.
                - Donations now follow a closer Schedule 9 flow, including the high-rate federal portion above the 2025 taxable-income threshold.
                - Ontario LIFT credit is estimated using Schedule ON428-A style thresholds for 2025.
                - Eligible dependant auto-claims now respect the key restrictions you enter: spouse status, separation, living arrangement, support payments, and household exclusivity.
                - Refund or balance owing = income tax withheld + instalments + refundable credits + other payments - total income tax payable.
                """
            )


def empty_rows(columns: list[str], rows: int = 3) -> list[dict]:
    return [{column: 0.0 for column in columns} for _ in range(rows)]


def render_t_slip_wizard_card(title: str, card_key: str, fields: list[dict[str, object]], count_default: int = 1) -> list[dict[str, float]]:
    st.markdown(f"#### {title}")
    microcopy = SLIP_WIZARD_MICROCOPY.get(card_key, {})
    if microcopy.get("should_fill"):
        st.caption(f"Should you fill this? {microcopy['should_fill']}")
    if microcopy.get("tip"):
        st.caption(f"Quick tip: {microcopy['tip']}")
    count = int(
        st.number_input(
            f"Number of {title}",
            min_value=0,
            step=1,
            value=int(st.session_state.get(f"{card_key}_count", count_default)),
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
                record[field_id] = float(
                    col.number_input(
                        str(field["label"]),
                        min_value=0.0,
                        step=float(field.get("step", 100.0)),
                        value=float(st.session_state.get(f"{card_key}_{index}_{field_id}", 0.0)),
                        key=f"{card_key}_{index}_{field_id}",
                        help=str(field.get("help", "")) if field.get("help") else None,
                    )
                )
            records.append(record)
    st.session_state[card_key] = records
    return records


def get_state_number(key: str, default: float = 0.0) -> float:
    return float(st.session_state.get(key, default) or 0.0)


def get_state_bool(key: str, default: bool = False) -> bool:
    return bool(st.session_state.get(key, default))


def get_state_text(key: str, default: str = "") -> str:
    return str(st.session_state.get(key, default) or default)


STEP_SCROLL_TARGETS = {
    "slips": "1-upload-slips",
    "review_slips": "2-review-slip-values",
    "questions": "3-quick-questions",
    "review_return": "4-review-return",
    "results": "6-results",
}
SLIP_TYPE_LABELS = {str(config["key"]): str(config["title"]) for config in SLIP_WIZARD_CONFIGS}
LOW_CONFIDENCE_THRESHOLD = 0.88
LOW_CONFIDENCE_FIELD_THRESHOLD = 0.86


def render_step_heading(title: str, anchor_id: str) -> None:
    st.markdown(
        f"""
        <h3 id="{anchor_id}" style="margin: 0 0 0.25rem 0; padding: 0;">
            {title}
        </h3>
        """,
        unsafe_allow_html=True,
    )


def queue_step_scroll(step_id: str) -> None:
    st.session_state["pending_scroll_anchor"] = STEP_SCROLL_TARGETS.get(step_id, "")


def render_upload_extraction_feedback() -> None:
    extraction_summary = st.session_state.get("upload_extraction_summary") or {}
    processed_count = int(extraction_summary.get("processed_count", 0) or 0)
    recognized_labels = list(extraction_summary.get("recognized_labels", []))
    unrecognized_files = list(extraction_summary.get("unrecognized_files", []))
    low_confidence_files = list(extraction_summary.get("low_confidence_files", []))
    if processed_count <= 0:
        return
    st.success("Slip extraction completed. Please review the summary below, then click Next to continue.")
    summary_rows = [
        {"Item": "Slips processed", "Value": str(processed_count)},
        {"Item": "Recognized slip types", "Value": ", ".join(recognized_labels) if recognized_labels else "None"},
        {"Item": "Needs manual review", "Value": ", ".join(unrecognized_files) if unrecognized_files else "None"},
        {"Item": "Recognized but should still be checked", "Value": ", ".join(low_confidence_files) if low_confidence_files else "None"},
    ]
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    if unrecognized_files:
        st.warning("Some files could not be matched confidently. Please review those slips manually, or continue later with manual amounts if needed.")
    if low_confidence_files:
        st.info("Some recognized slips used OCR fallback or lower-confidence extraction. Please check those values carefully in Review Slip Values.")


def parser_review_summary(parser_review: dict | None, fields: list[dict[str, object]]) -> tuple[list[str], str | None]:
    if not parser_review:
        return [], "This slip was loaded without parser review details. Please double-check the extracted values."
    confidence_map = parser_review.get("confidence", {}) or {}
    flagged_fields = [
        str(field["label"])
        for field in fields
        if confidence_map.get(str(field["id"]), 1.0) < LOW_CONFIDENCE_FIELD_THRESHOLD
    ]
    meta = parser_review.get("meta", {}) or {}
    avg_conf = float(meta.get("avg_confidence", 0.0) or 0.0)
    fallback_used = bool(meta.get("text_fallback_triggered", False))
    if flagged_fields:
        return flagged_fields, None
    if avg_conf and avg_conf < LOW_CONFIDENCE_THRESHOLD:
        return [], "This slip was recognized, but the overall extraction confidence was lower than usual. Please double-check the values below."
    if fallback_used:
        return [], "This slip used OCR fallback during extraction. Please review the values before continuing."
    return [], None


def build_results_tab_names() -> tuple[list[str], str | None]:
    tab_names = [
        "Summary",
        "Return Details",
        "Review Checks",
        "Foreign Tax Credit",
        "ON428",
        "Rental Details",
        "Capital Gains",
        "Tuition",
        "Donations",
        "Scope / Limits",
        "ON479",
    ]
    return tab_names, "ON479"


def build_results_summary_signal_inputs(
    session_state,
    result: dict,
    tax_year: int,
    province: str,
    age: float | int,
) -> tuple[dict[str, float], dict[str, object]]:
    wizard_totals = {
        "t3": float(bool(session_state.get("t3_wizard", []))),
        "t5": float(bool(session_state.get("t5_wizard", []))),
    }
    raw_inputs = {
        "tax_year": tax_year,
        "province": province,
        "age": age,
        "spouse_claim_enabled": session_state.get("spouse_claim_enabled", False),
        "has_spouse_end_of_year": session_state.get("has_spouse_end_of_year", False),
        "separated_in_year": session_state.get("separated_in_year", False),
        "support_payments_to_spouse": session_state.get("support_payments_to_spouse", False),
        "spouse_infirm": session_state.get("spouse_infirm", False),
        "eligible_dependant_claim_enabled": session_state.get("eligible_dependant_claim_enabled", False),
        "dependant_lived_with_you": session_state.get("dependant_lived_with_you", False),
        "dependant_relationship": session_state.get("dependant_relationship", ""),
        "dependant_category": session_state.get("dependant_category", ""),
        "paid_child_support_for_dependant": session_state.get("paid_child_support_for_dependant", False),
        "shared_custody_claim_agreement": session_state.get("shared_custody_claim_agreement", False),
        "another_household_member_claims_dependant": session_state.get("another_household_member_claims_dependant", False),
        "cwb_basic_eligible": session_state.get("cwb_basic_eligible", False),
        "cwb_disability_supplement_eligible": session_state.get("cwb_disability_supplement_eligible", False),
        "spouse_cwb_disability_supplement_eligible": session_state.get("spouse_cwb_disability_supplement_eligible", False),
        "medical_expenses_paid": session_state.get("medical_expenses_paid", 0.0),
        "charitable_donations": session_state.get("charitable_donations", 0.0),
        "donations_eligible_total": session_state.get("donations_eligible_total", 0.0),
        "moving_expenses": session_state.get("moving_expenses", 0.0),
        "child_care_expenses": session_state.get("child_care_expenses", 0.0),
        "other_employment_expenses": session_state.get("other_employment_expenses", 0.0),
        "rrsp_deduction": session_state.get("rrsp_deduction", 0.0),
        "fhsa_deduction": session_state.get("fhsa_deduction", 0.0),
        "support_payments_deduction": session_state.get("support_payments_deduction", 0.0),
        "foreign_income": session_state.get("foreign_income", 0.0),
        "foreign_tax_paid": session_state.get("foreign_tax_paid", 0.0),
        "interest_income": session_state.get("interest_income", 0.0),
        "eligible_dividends": session_state.get("eligible_dividends", 0.0),
        "non_eligible_dividends": session_state.get("non_eligible_dividends", 0.0),
        "student_loan_interest": session_state.get("student_loan_interest", 0.0),
        "tuition_amount_claim": session_state.get("tuition_amount_claim", 0.0),
        "schedule11_current_year_tuition_available": result.get("schedule11_current_year_tuition_available", 0.0),
        "schedule11_carryforward_available": result.get("schedule11_carryforward_available", 0.0),
        "canada_training_credit_limit_available": session_state.get("canada_training_credit_limit_available", 0.0),
        "bc_renters_credit_eligible": session_state.get("bc_renters_credit_eligible", False),
        "t776_property_taxes": session_state.get("t776_property_taxes", 0.0),
        "canada_workers_benefit": session_state.get("canada_workers_benefit", 0.0),
        "canada_training_credit": session_state.get("canada_training_credit", 0.0),
        "medical_expense_supplement": session_state.get("medical_expense_supplement", 0.0),
        "other_federal_refundable_credits": session_state.get("other_federal_refundable_credits", 0.0),
        "manual_provincial_refundable_credits": session_state.get("manual_provincial_refundable_credits", 0.0),
        "refundable_credits": session_state.get("refundable_credits", 0.0),
        "spouse_amount_claim": session_state.get("spouse_amount_claim", 0.0),
        "eligible_dependant_claim": session_state.get("eligible_dependant_claim", 0.0),
        "spouse_net_income": session_state.get("spouse_net_income", 0.0),
        "income_tax_withheld": session_state.get("income_tax_withheld", 0.0),
        "cpp_withheld": session_state.get("cpp_withheld", 0.0),
        "ei_withheld": session_state.get("ei_withheld", 0.0),
        "installments_paid": session_state.get("installments_paid", 0.0),
        "other_payments": session_state.get("other_payments", 0.0),
        "t2209_non_business_tax_paid": session_state.get("t2209_non_business_tax_paid", 0.0),
        "t2209_net_foreign_non_business_income": session_state.get("t2209_net_foreign_non_business_income", 0.0),
        "t2209_net_income_override": session_state.get("t2209_net_income_override", 0.0),
        "t2209_basic_federal_tax_override": session_state.get("t2209_basic_federal_tax_override", 0.0),
        "t2036_provincial_tax_otherwise_payable_override": session_state.get("t2036_provincial_tax_otherwise_payable_override", 0.0),
    }
    return wizard_totals, raw_inputs


def build_results_summary_suggestions(
    session_state,
    result: dict,
    readiness_df: pd.DataFrame,
    tax_year: int,
    province: str,
    province_name: str,
    age: float | int,
) -> list[SuggestionItem]:
    wizard_totals, raw_inputs = build_results_summary_signal_inputs(
        session_state=session_state,
        result=result,
        tax_year=tax_year,
        province=province,
        age=age,
    )
    screening = build_screening_inputs(
        province=province,
        province_name=province_name,
        session_state=session_state,
        wizard_totals=wizard_totals,
        raw_inputs=raw_inputs,
    )
    eligibility_decision = build_eligibility_decision(
        tax_year=tax_year,
        province=province,
        age=float(age or 0.0),
        raw_inputs=raw_inputs,
        result=result,
    )
    progress = build_section_progress(
        session_state=session_state,
        wizard_totals=wizard_totals,
        raw_inputs=raw_inputs,
        result=result,
        eligibility_decision=eligibility_decision,
    )
    guidance_items = build_eligibility_guidance(screening, eligibility_decision, progress)
    completion_flags = build_completion_flags(
        screening=screening,
        progress=progress,
        wizard_totals=wizard_totals,
        raw_inputs=raw_inputs,
        result=result,
        readiness_df=readiness_df,
        eligibility_decision=eligibility_decision,
    )
    return build_suggestions(
        screening=screening,
        guidance_items=guidance_items,
        progress=progress,
        completion_flags=completion_flags,
    )


def normalize_ontario_mvp_hidden_state() -> None:
    hidden_false_keys = [
        "separated_in_year",
        "support_payments_to_spouse",
        "spouse_infirm",
        "eligible_dependant_infirm",
        "paid_child_support_for_dependant",
        "shared_custody_claim_agreement",
        "another_household_member_claims_dependant",
        "another_household_member_claims_caregiver",
        "another_household_member_claims_disability_transfer",
        "medical_dependant_claim_shared",
        "spouse_disability_transfer_available",
        "dependant_disability_transfer_available",
    ]
    hidden_zero_keys = [
        "spouse_disability_transfer_available_amount",
        "dependant_disability_transfer_available_amount",
        "provincial_caregiver_claim_amount",
        "ontario_disability_transfer",
        "ontario_medical_dependants",
        "line_21300",
        "rdsp_repayment",
        "universal_child_care_benefit",
        "rdsp_income",
        "spouse_line_21300",
        "spouse_rdsp_repayment",
        "spouse_uccb",
        "spouse_rdsp_income",
    ]
    for key in hidden_false_keys:
        st.session_state[key] = False
    for key in hidden_zero_keys:
        st.session_state[key] = 0.0


def persist_mvp_question_state() -> None:
    q_has_spouse_value = st.session_state.get("q_has_spouse")
    if q_has_spouse_value in {"Yes", "No"}:
        st.session_state["mvp_has_spouse_end_of_year"] = q_has_spouse_value == "Yes"

    if "spouse_claim_enabled" in st.session_state:
        st.session_state["mvp_spouse_claim_enabled"] = bool(st.session_state.get("spouse_claim_enabled", False))
    if "spouse_net_income" in st.session_state:
        st.session_state["mvp_spouse_net_income"] = float(st.session_state.get("spouse_net_income", 0.0) or 0.0)

    q_check_cwb_value = st.session_state.get("q_check_cwb")
    if q_check_cwb_value in {"Yes", "No"}:
        st.session_state["mvp_check_cwb"] = q_check_cwb_value == "Yes"

    if "cwb_basic_eligible" in st.session_state:
        st.session_state["mvp_cwb_basic_eligible"] = bool(st.session_state.get("cwb_basic_eligible", False))
    if "cwb_disability_supplement_eligible" in st.session_state:
        st.session_state["mvp_cwb_disability_supplement_eligible"] = bool(
            st.session_state.get("cwb_disability_supplement_eligible", False)
        )
    if "spouse_cwb_disability_supplement_eligible" in st.session_state:
        st.session_state["mvp_spouse_cwb_disability_supplement_eligible"] = bool(
            st.session_state.get("spouse_cwb_disability_supplement_eligible", False)
        )


def render_pending_step_scroll() -> None:
    anchor_id = get_state_text("pending_scroll_anchor")
    if not anchor_id:
        return
    components.html(
        f"""
        <script>
        (() => {{
            const anchorId = "{anchor_id}";
            const targetHash = "#" + anchorId;
            const parentWindow = window.parent;
            const parentDocument = parentWindow.document;
            const getScrollContainers = () => {{
                const selectors = [
                    'section.main',
                    '[data-testid="stAppViewContainer"]',
                    '[data-testid="stMain"]',
                    '.main',
                    '.stApp',
                    'body',
                    'html'
                ];
                const containers = [];
                selectors.forEach((selector) => {{
                    parentDocument.querySelectorAll(selector).forEach((node) => containers.push(node));
                }});
                containers.push(parentDocument.scrollingElement);
                return [...new Set(containers.filter(Boolean))];
            }};

            const scrollToAnchor = () => {{
                const target =
                    parentDocument.getElementById(anchorId) ||
                    parentDocument.querySelector(`[id="${{anchorId}}"]`);
                if (!target) {{
                    return false;
                }}
                parentWindow.history.replaceState(null, "", targetHash);
                const absoluteTop = target.getBoundingClientRect().top + parentWindow.pageYOffset - 8;
                target.scrollIntoView({{ behavior: "auto", block: "start", inline: "nearest" }});
                parentWindow.scrollTo(0, absoluteTop);
                parentDocument.documentElement.scrollTop = absoluteTop;
                parentDocument.body.scrollTop = absoluteTop;
                getScrollContainers().forEach((container) => {{
                    try {{
                        container.scrollTop = absoluteTop;
                    }} catch (error) {{}}
                }});
                return true;
            }};

            let attempts = 0;
            const maxAttempts = 40;
            const tick = () => {{
                attempts += 1;
                const success = scrollToAnchor();
                if (!success && attempts < maxAttempts) {{
                    parentWindow.requestAnimationFrame(tick);
                    return;
                }}
                if (attempts < maxAttempts) {{
                    parentWindow.setTimeout(() => {{
                        parentWindow.requestAnimationFrame(tick);
                    }}, 120);
                }}
            }};

            parentWindow.requestAnimationFrame(tick);
        }})();
        </script>
        """,
        height=0,
    )
    st.session_state["pending_scroll_anchor"] = ""


def render_mvp_step_shell() -> str:
    steps = [
        ("slips", "1. Slips"),
        ("review_slips", "2. Review"),
        ("questions", "3. Questions"),
        ("review_return", "4. Review"),
        ("results", "5. Results"),
    ]
    step_ids = [step_id for step_id, _ in steps]
    current_step = get_state_text("mvp_step", "slips")
    if current_step not in step_ids:
        current_step = "slips"
        st.session_state["mvp_step"] = current_step
    if st.session_state.get("mvp_step_selector") != current_step:
        st.session_state["mvp_step_selector"] = current_step

    with st.container(border=True):
        st.caption("Ontario MVP flow")
        selected_step = st.radio(
            "Progress",
            step_ids,
            index=step_ids.index(current_step),
            key="mvp_step_selector",
            format_func=lambda step_id: dict(steps)[step_id],
            horizontal=True,
            label_visibility="collapsed",
        )
        if selected_step != current_step:
            st.session_state["mvp_step"] = selected_step
            queue_step_scroll(selected_step)
            current_step = selected_step
        st.caption("Start with slips, answer a few review questions, then calculate an Ontario estimate. Manually review unsupported cases and any values flagged for checking.")
    return current_step


def render_mvp_step_footer(
    current_step: str,
    *,
    next_disabled: bool = False,
    next_label: str = "Next",
    show_next: bool = True,
    show_reset: bool = False,
    helper_text: str = "Complete the section above, then continue.",
) -> None:
    step_ids = ["slips", "review_slips", "questions", "review_return", "results"]
    current_index = step_ids.index(current_step)
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 4])
    with nav_col1:
        if current_index > 0 and st.button("Back", key=f"{current_step}_step_back", use_container_width=True):
            previous_step = step_ids[current_index - 1]
            st.session_state["mvp_step"] = previous_step
            queue_step_scroll(previous_step)
            st.rerun()
        if show_reset and st.button("Reset", key=f"{current_step}_step_reset", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    with nav_col2:
        if show_next and current_index < len(step_ids) - 1:
            if st.button(next_label, key=f"{current_step}_step_next", use_container_width=True, disabled=next_disabled):
                next_step = step_ids[current_index + 1]
                st.session_state["mvp_step"] = next_step
                queue_step_scroll(next_step)
                st.rerun()
    with nav_col3:
        st.caption(helper_text)


def render_slip_review_cards(configs: list[dict[str, object]]) -> dict[str, list[dict[str, float]]]:
    records_by_key: dict[str, list[dict[str, float]]] = {}
    for config in configs:
        card_key = str(config["key"])
        count_key = f"{card_key}_count"
        current_count = int(st.session_state.get(count_key, 0) or 0)
        if current_count <= 0:
            records_by_key[card_key] = []
            continue

        deduped_records: list[dict[str, float]] = []
        deduped_reviews: list[dict] = []
        seen_signatures: set[tuple[tuple[str, float], ...]] = set()
        for index in range(current_count):
            record = {
                str(field["id"]): float(st.session_state.get(f"{card_key}_{index}_{field['id']}", 0.0) or 0.0)
                for field in config["fields"]
            }
            parser_review = st.session_state.get(f"{card_key}_{index}__parser_review")
            signature = tuple(sorted(record.items()))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            deduped_records.append(record)
            deduped_reviews.append(parser_review)

        if len(deduped_records) != current_count:
            st.session_state[count_key] = len(deduped_records)
            for index, record in enumerate(deduped_records):
                for field_id, value in record.items():
                    st.session_state[f"{card_key}_{index}_{field_id}"] = value
                if index < len(deduped_reviews):
                    st.session_state[f"{card_key}_{index}__parser_review"] = deduped_reviews[index]

        records = render_t_slip_wizard_card(
            str(config["title"]),
            card_key,
            list(config["fields"]),
            count_default=max(1, len(deduped_records)),
        )
        records_by_key[card_key] = records
        if records:
            for index in range(len(records)):
                parser_review = st.session_state.get(f"{card_key}_{index}__parser_review")
                flagged_fields, note = parser_review_summary(parser_review, list(config["fields"]))
                if flagged_fields:
                    st.warning(
                        f"{config['title']} #{index + 1}: Please double-check these extracted fields: {', '.join(flagged_fields)}."
                    )
                elif note:
                    st.info(f"{config['title']} #{index + 1}: {note}")
            confirmation_key = f"{card_key}_reviewed"
            st.checkbox(
                f"I reviewed the {config['title']} entries above",
                value=bool(st.session_state.get(confirmation_key, False)),
                key=confirmation_key,
            )
    return records_by_key


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
debug_mode = bool(st.session_state.get("debug_mode", False))

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
st.subheader(
    "Ontario T1 Semi-Auto Tax Review & Optimization",
    help="This is an Ontario-first tax estimate and review tool. It helps you extract slip data, review key amounts, and estimate a personal T1 result, but it is not CRA-certified filing software.",
)

with st.expander("Scope and assumptions", expanded=False):
    st.markdown(
        """
        - This MVP is designed as an `estimate and review tool`, not a CRA-certified filing or transmission product.
        - It currently focuses on Ontario personal T1 returns built mainly from common slips and common follow-up items.
        - Some benefits are shown as separate recommendations only and are `not automatically included` in the estimate.
        - Self-employment / T2125, filing transmission, and unsupported complex cases still need manual handling or separate software.
        - You should manually review unsupported slips, low-confidence extracted values, carryforwards, and unusual household or benefit situations before filing.
        """
    )

with st.container(border=True):
    st.caption("Return setup")
    setup_col1, setup_col2, setup_col3 = st.columns(3)
    tax_year = setup_col1.selectbox("Tax Year", AVAILABLE_TAX_YEARS, key="tax_year")
    province = setup_col2.selectbox(
        "Province",
        ["ON"],
        index=0,
        key="province",
        format_func=lambda code: PROVINCES[code],
        disabled=True,
        help="Ontario is the only province available in the current MVP flow.",
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
            - `Most Ontario users:` upload slips, confirm the values, answer a few quick questions, then calculate.
            - `Only have slips?` You can often finish with very little manual input.
            - `Have rental, capital gains, RRSP/FHSA, spouse, or medical/donation items?` The Questions step will ask just enough to cover them.
            """
        )
province_name = PROVINCES[province]

mvp_step = render_mvp_step_shell()

uploaded_slip_count = sum(
    int(st.session_state.get(f"{config['key']}_count", 0) or 0)
    for config in SLIP_WIZARD_CONFIGS
)

uploaded_files = []
if mvp_step == "slips":
    render_step_heading("1. Upload Slips", "1-upload-slips")
    st.caption("Best fit for T4, T4A, T5, T3, T4PS, and T2202. Start here even if you may have a few extra deductions later.")
    uploaded_files = st.file_uploader(
        "Upload T-Slips (PDF/Scanned Images)",
        accept_multiple_files=True,
    )
    if uploaded_files and st.button("Extract Data", type="primary"):
        processed_count = 0
        recognized_keys: list[str] = []
        unrecognized_files: list[str] = []
        low_confidence_files: list[str] = []
        with st.spinner("Reading your slips..."):
            for f in uploaded_files:
                processed_count += 1
                temp_path = f"tmp_{f.name}"
                with open(temp_path, "wb") as w:
                    w.write(f.getbuffer())

                result = parse_pdf_slip(temp_path, f.name)
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

                if result["type"] != "UNKNOWN":
                    wizard_key = result["type"].lower() + "_wizard"
                    if wizard_key not in recognized_keys:
                        recognized_keys.append(wizard_key)
                    current_count = int(st.session_state.get(f"{wizard_key}_count", 0))
                    for key, val in result["data"].items():
                        st.session_state[f"{wizard_key}_{current_count}_{key}"] = val
                    st.session_state[f"{wizard_key}_{current_count}__parser_review"] = {
                        "confidence": dict(result.get("confidence", {})),
                        "evidence": dict(result.get("evidence", {})),
                        "meta": dict(result.get("meta", {})),
                        "filename": f.name,
                    }
                    avg_confidence = float((result.get("meta", {}) or {}).get("avg_confidence", 0.0) or 0.0)
                    fallback_used = bool((result.get("meta", {}) or {}).get("text_fallback_triggered", False))
                    low_confidence_field_count = sum(
                        1 for value in dict(result.get("confidence", {})).values()
                        if float(value or 0.0) < LOW_CONFIDENCE_FIELD_THRESHOLD
                    )
                    if avg_confidence < LOW_CONFIDENCE_THRESHOLD or fallback_used or low_confidence_field_count > 0:
                        low_confidence_files.append(f.name)
                    st.session_state[f"{wizard_key}_count"] = current_count + 1
                    st.success(f"Processed {f.name} as {result['type']}.")
                else:
                    unrecognized_files.append(f.name)
                    st.warning(f"{f.name} could not be matched to a supported slip type.")
        st.session_state["upload_extraction_summary"] = {
            "processed_count": processed_count,
            "recognized_labels": [SLIP_TYPE_LABELS.get(key, key) for key in recognized_keys],
            "unrecognized_files": unrecognized_files,
            "low_confidence_files": low_confidence_files,
        }
        st.session_state["upload_extracted_notice"] = True
        st.rerun()
    if get_state_bool("upload_extracted_notice") and st.session_state.get("upload_extraction_summary", {}).get("processed_count", 0):
        render_upload_extraction_feedback()
    render_mvp_step_footer(
        "slips",
        next_disabled=uploaded_slip_count == 0,
        helper_text="Upload and extract at least one supported slip before continuing.",
    )

if mvp_step == "review_slips":
    render_step_heading("2. Review Slip Values", "2-review-slip-values")
    st.caption("Check the key boxes below. Most people only need to confirm these values before moving on.")
    wizard_records = render_slip_review_cards(SLIP_WIZARD_CONFIGS)
else:
    wizard_records = {
        "t4_wizard": st.session_state.get("t4_wizard", []),
        "t4a_wizard": st.session_state.get("t4a_wizard", []),
        "t5_wizard": st.session_state.get("t5_wizard", []),
        "t3_wizard": st.session_state.get("t3_wizard", []),
        "t4ps_wizard": st.session_state.get("t4ps_wizard", []),
        "t2202_wizard": st.session_state.get("t2202_wizard", []),
    }

t4_wizard_records = wizard_records["t4_wizard"]
t4a_wizard_records = wizard_records["t4a_wizard"]
t5_wizard_records = wizard_records["t5_wizard"]
t3_wizard_records = wizard_records["t3_wizard"]
t4ps_wizard_records = wizard_records["t4ps_wizard"]
t2202_wizard_records = wizard_records["t2202_wizard"]

review_required_keys = [
    str(config["key"])
    for config in SLIP_WIZARD_CONFIGS
    if int(st.session_state.get(f"{config['key']}_count", 0) or 0) > 0
]
review_complete = all(get_state_bool(f"{key}_reviewed") for key in review_required_keys) if review_required_keys else False
if mvp_step == "review_slips":
    render_mvp_step_footer(
        "review_slips",
        next_disabled=not review_complete,
        helper_text="Review each uploaded slip and tick the confirmation box before continuing.",
    )

if mvp_step == "questions":
    render_step_heading("3. Quick Questions", "3-quick-questions")
    st.caption("Only answer the items that apply to you. Most fields stay hidden unless you answer Yes.")

rental_schedule_df = pd.DataFrame(
    columns=[
        "property_label",
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
    ]
)
capital_schedule_df = pd.DataFrame(columns=["description", "property_type", "proceeds", "acb", "outlays"])

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

if mvp_step == "questions":
    st.markdown("#### Most Common Questions")
    st.caption("Start with the 7 most common Ontario follow-up items. Open the less common section only if needed.")
    with st.container(border=True):
        st.markdown("#### Core Deductions")
        if st.radio("Did you contribute to RRSP?", ["No", "Yes"], horizontal=True, key="q_has_rrsp") == "Yes":
            number_input("RRSP Deduction Claimed", "rrsp_deduction", 500.0)
        if st.radio("Did you have deductible work expenses?", ["No", "Yes"], horizontal=True, key="q_has_work_expenses") == "Yes":
            number_input("Other Employment Expenses", "other_employment_expenses", 100.0)

    with st.container(border=True):
        st.markdown("#### Core Credits")
        if st.radio("Did you have medical expenses?", ["No", "Yes"], horizontal=True, key="q_has_medical") == "Yes":
            number_input("Medical Expenses Paid", "medical_expenses_paid", 100.0)
        if st.radio("Did you make charitable donations?", ["No", "Yes"], horizontal=True, key="q_has_donations") == "Yes":
            number_input("Charitable Donations", "charitable_donations", 100.0)

    with st.container(border=True):
        st.markdown("#### Benefits")
        if st.radio("Do you want us to check Canada Workers Benefit (CWB)?", ["No", "Yes"], horizontal=True, key="q_check_cwb") == "Yes":
            st.session_state["cwb_basic_eligible"] = True
            st.caption("CWB basic eligibility check is now on for this return.")
            st.checkbox(
                "Check CWB disability supplement eligibility",
                value=bool(st.session_state.get("cwb_disability_supplement_eligible", False)),
                key="cwb_disability_supplement_eligible",
            )
            if get_state_bool("has_spouse_end_of_year"):
                st.checkbox(
                    "Check spouse CWB disability supplement eligibility",
                    value=bool(st.session_state.get("spouse_cwb_disability_supplement_eligible", False)),
                    key="spouse_cwb_disability_supplement_eligible",
                )
        else:
            st.session_state["cwb_basic_eligible"] = False
            st.session_state["cwb_disability_supplement_eligible"] = False
            st.session_state["spouse_cwb_disability_supplement_eligible"] = False

    with st.container(border=True):
        st.markdown("#### Household")
        if st.radio(
            "Did you have a spouse or common-law partner at year end?",
            ["No", "Yes"],
            horizontal=True,
            key="q_has_spouse",
            help="If yes, we can check whether you may qualify for the spouse or common-law partner amount tax credit.",
        ) == "Yes":
            st.session_state["has_spouse_end_of_year"] = True
            st.caption("If you claim the spouse amount and your spouse or common-law partner had low net income, you may qualify for a tax credit.")
            st.checkbox("Check spouse amount eligibility", value=bool(st.session_state.get("spouse_claim_enabled", True)), key="spouse_claim_enabled")
            number_input("Spouse Net Income", "spouse_net_income", 100.0)
        else:
            st.session_state["has_spouse_end_of_year"] = False

    with st.container(border=True):
        st.markdown("#### Payments")
        if st.radio("Did you make instalments or other tax payments outside your slips?", ["No", "Yes"], horizontal=True, key="q_has_payments") == "Yes":
            number_input("Tax Instalments Paid", "installments_paid", 100.0)
            number_input("Other Tax Payments / Credits", "other_payments", 100.0)

    with st.expander("Less Common Questions", expanded=False):
        st.caption("Open this only if any of these extra items apply to you.")
        with st.container(border=True):
            st.markdown("#### Extra Income")
            rental_toggle = st.radio(
                "Do you have rental income not already shown on slips?",
                ["No", "Yes"],
                horizontal=True,
                key="q_has_rental_income",
            )
            if rental_toggle == "Yes":
                number_input("Net Rental Income", "net_rental_income", 500.0)
            gains_toggle = st.radio(
                "Do you have capital gains or losses not already captured on slips?",
                ["No", "Yes"],
                horizontal=True,
                key="q_has_capital_gains",
            )
            if gains_toggle == "Yes":
                number_input("Additional Taxable Capital Gains", "taxable_capital_gains", 500.0)
                number_input("Net Capital Loss Carryforward Used", "net_capital_loss_carryforward", 100.0)
            other_income_toggle = st.radio(
                "Do you have other taxable income not already shown on slips?",
                ["No", "Yes"],
                horizontal=True,
                key="q_has_other_income",
            )
            if other_income_toggle == "Yes":
                number_input("Other Taxable Income", "other_income", 500.0)
            investment_toggle = st.radio(
                "Do you have extra interest or dividend income not already captured on slips?",
                ["No", "Yes"],
                horizontal=True,
                key="q_has_investment_income",
            )
            if investment_toggle == "Yes":
                number_input("Manual Interest / Investment Income", "interest_income", 100.0)
                number_input("Eligible Dividends", "eligible_dividends", 100.0)
                number_input("Non-Eligible Dividends", "non_eligible_dividends", 100.0)

        with st.container(border=True):
            st.markdown("#### Other Deductions And Credits")
            if st.radio("Did you contribute to FHSA?", ["No", "Yes"], horizontal=True, key="q_has_fhsa") == "Yes":
                number_input("FHSA Deduction Claimed", "fhsa_deduction", 500.0)
            if st.radio("Did you have child care expenses?", ["No", "Yes"], horizontal=True, key="q_has_child_care") == "Yes":
                number_input("Child Care Expenses", "child_care_expenses", 100.0)
            if st.radio("Did you have moving expenses?", ["No", "Yes"], horizontal=True, key="q_has_moving") == "Yes":
                number_input("Moving Expenses", "moving_expenses", 100.0)
            if st.radio("Did you pay student loan interest?", ["No", "Yes"], horizontal=True, key="q_has_student_loan") == "Yes":
                number_input("Student Loan Interest", "student_loan_interest", 50.0)
            if st.radio("Do you have tuition or a T2202?", ["No", "Yes"], horizontal=True, key="q_has_tuition") == "Yes":
                number_input("Optional Additional Tuition Amount", "tuition_amount_claim", 100.0)
        with st.container(border=True):
            st.markdown("#### Dependants")
            if st.radio("Are you supporting a dependant you may claim?", ["No", "Yes"], horizontal=True, key="q_has_dependant") == "Yes":
                st.checkbox("Check eligible dependant amount", value=bool(st.session_state.get("eligible_dependant_claim_enabled", True)), key="eligible_dependant_claim_enabled")
                st.selectbox("Dependant Relationship", ["Child", "Parent/Grandparent", "Other relative", "Other"], key="dependant_relationship")
                st.selectbox("Dependant Type", ["Minor child", "Adult child", "Parent/Grandparent", "Other adult relative", "Other"], key="dependant_category")
                st.checkbox("Dependant lived with you", key="dependant_lived_with_you")
                number_input("Dependant Net Income", "eligible_dependant_net_income", 100.0)

persist_mvp_question_state()
normalize_ontario_mvp_hidden_state()

employment_income_manual = get_state_number("employment_income")
pension_income_manual = get_state_number("pension_income")
rrsp_rrif_income_manual = get_state_number("rrsp_rrif_income")
other_income_manual = get_state_number("other_income")
manual_net_rental_income = get_state_number("net_rental_income")
manual_taxable_capital_gains = get_state_number("taxable_capital_gains")
interest_income_manual = get_state_number("interest_income")
eligible_dividends = get_state_number("eligible_dividends")
non_eligible_dividends = get_state_number("non_eligible_dividends")
t5_eligible_dividends_taxable = get_state_number("t5_eligible_dividends_taxable")
t5_non_eligible_dividends_taxable = get_state_number("t5_non_eligible_dividends_taxable")
t5_federal_dividend_credit = get_state_number("t5_federal_dividend_credit")
t3_eligible_dividends_taxable = get_state_number("t3_eligible_dividends_taxable")
t3_non_eligible_dividends_taxable = get_state_number("t3_non_eligible_dividends_taxable")
t3_federal_dividend_credit = get_state_number("t3_federal_dividend_credit")
t2202_tuition_total = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0))
rrsp_deduction = get_state_number("rrsp_deduction")
fhsa_deduction = get_state_number("fhsa_deduction")
rpp_contribution = get_state_number("rpp_contribution") + float(t4_wizard_totals.get("box20_rpp", 0.0))
union_dues = get_state_number("union_dues") + float(t4_wizard_totals.get("box44_union_dues", 0.0))
child_care_expenses = get_state_number("child_care_expenses")
moving_expenses = get_state_number("moving_expenses")
support_payments_deduction = get_state_number("support_payments_deduction")
carrying_charges = get_state_number("carrying_charges")
other_employment_expenses = get_state_number("other_employment_expenses")
other_deductions = get_state_number("other_deductions")
net_capital_loss_carryforward = get_state_number("net_capital_loss_carryforward")
other_loss_carryforward = get_state_number("other_loss_carryforward")
spouse_amount_claim = get_state_number("spouse_amount_claim")
spouse_net_income = get_state_number("spouse_net_income")
spouse_claim_enabled = get_state_bool("spouse_claim_enabled")
spouse_infirm = get_state_bool("spouse_infirm")
has_spouse_end_of_year = get_state_bool("has_spouse_end_of_year")
separated_in_year = get_state_bool("separated_in_year")
support_payments_to_spouse = get_state_bool("support_payments_to_spouse")
eligible_dependant_claim = get_state_number("eligible_dependant_claim")
eligible_dependant_net_income = get_state_number("eligible_dependant_net_income")
eligible_dependant_claim_enabled = get_state_bool("eligible_dependant_claim_enabled")
eligible_dependant_infirm = get_state_bool("eligible_dependant_infirm")
dependant_relationship = get_state_text("dependant_relationship", "Child")
dependant_category = get_state_text("dependant_category", "Minor child")
dependant_lived_with_you = get_state_bool("dependant_lived_with_you")
paid_child_support_for_dependant = get_state_bool("paid_child_support_for_dependant")
shared_custody_claim_agreement = get_state_bool("shared_custody_claim_agreement")
another_household_member_claims_dependant = get_state_bool("another_household_member_claims_dependant")
another_household_member_claims_caregiver = get_state_bool("another_household_member_claims_caregiver")
another_household_member_claims_disability_transfer = get_state_bool("another_household_member_claims_disability_transfer")
medical_dependant_claim_shared = get_state_bool("medical_dependant_claim_shared")
spouse_disability_transfer_available = get_state_bool("spouse_disability_transfer_available")
spouse_disability_transfer_available_amount = get_state_number("spouse_disability_transfer_available_amount")
dependant_disability_transfer_available = get_state_bool("dependant_disability_transfer_available")
dependant_disability_transfer_available_amount = get_state_number("dependant_disability_transfer_available_amount")
additional_dependants_df = pd.DataFrame(columns=["dependant_label", "category", "infirm", "lived_with_you", "caregiver_claim_amount", "disability_transfer_available_amount", "medical_expenses_amount", "medical_claim_shared"])
additional_dependant_count = 0
additional_dependant_caregiver_claim_total = 0.0
additional_dependant_disability_transfer_available_total = 0.0
additional_dependant_medical_claim_total = 0.0
caregiver_claim_target = get_state_text("caregiver_claim_target", "Auto")
disability_transfer_source = get_state_text("disability_transfer_source", "Auto")
disability_amount_claim = get_state_number("disability_amount_claim")
age_amount_claim = get_state_number("age_amount_claim")
student_loan_interest = get_state_number("student_loan_interest")
medical_expenses_eligible = get_state_number("medical_expenses_eligible")
medical_expenses_paid = get_state_number("medical_expenses_paid")
charitable_donations = get_state_number("charitable_donations")
refundable_credits = get_state_number("refundable_credits")
tuition_amount_claim = get_state_number("tuition_amount_claim")
tuition_transfer_from_spouse = get_state_number("tuition_transfer_from_spouse")
additional_federal_credits = get_state_number("additional_federal_credits")
additional_provincial_credit_amount = get_state_number("additional_provincial_credit_amount")
canada_workers_benefit = get_state_number("canada_workers_benefit")
cwb_basic_eligible = get_state_bool("cwb_basic_eligible")
cwb_disability_supplement_eligible = get_state_bool("cwb_disability_supplement_eligible")
spouse_cwb_disability_supplement_eligible = get_state_bool("spouse_cwb_disability_supplement_eligible")
canada_training_credit_limit_available = get_state_number("canada_training_credit_limit_available")
canada_training_credit = get_state_number("canada_training_credit")
medical_expense_supplement = get_state_number("medical_expense_supplement")
other_federal_refundable_credits = get_state_number("other_federal_refundable_credits")
manual_provincial_refundable_credits = get_state_number("manual_provincial_refundable_credits")
ontario_caregiver_amount = get_state_number("provincial_caregiver_claim_amount")
ontario_student_loan_interest = get_state_number("ontario_student_loan_interest")
ontario_tuition_transfer = get_state_number("ontario_tuition_transfer")
ontario_disability_transfer = get_state_number("ontario_disability_transfer")
ontario_adoption_expenses = get_state_number("ontario_adoption_expenses")
ontario_medical_dependants = get_state_number("ontario_medical_dependants")
ontario_dependent_children_count = int(st.session_state.get("provincial_dependent_children_count", 0) or 0)
ontario_dependant_impairment_count = int(st.session_state.get("ontario_dependant_impairment_count", 0) or 0)
foreign_income = get_state_number("foreign_income") + float(t5_wizard_totals.get("box15_foreign_income", 0.0)) + float(t3_wizard_totals.get("box25_foreign_income", 0.0)) + float(t4ps_wizard_totals.get("box37_foreign_non_business_income", 0.0))
foreign_tax_paid = get_state_number("foreign_tax_paid") + float(t5_wizard_totals.get("box16_foreign_tax_paid", 0.0)) + float(t3_wizard_totals.get("box34_foreign_tax_paid", 0.0))
t2209_non_business_tax_paid = get_state_number("t2209_non_business_tax_paid")
t2209_net_foreign_non_business_income = get_state_number("t2209_net_foreign_non_business_income")
t2209_net_income_override = get_state_number("t2209_net_income_override")
t2209_basic_federal_tax_override = get_state_number("t2209_basic_federal_tax_override")
t2036_provincial_tax_otherwise_payable_override = get_state_number("t2036_provincial_tax_otherwise_payable_override")
ontario_dividend_tax_credit_manual = get_state_number("provincial_dividend_tax_credit_manual")
donations_eligible_total = get_state_number("donations_eligible_total")
ecological_cultural_gifts = get_state_number("ecological_cultural_gifts")
ecological_gifts_pre2016 = get_state_number("ecological_gifts_pre2016")
income_tax_withheld = get_state_number("income_tax_withheld")
cpp_withheld = get_state_number("cpp_withheld")
ei_withheld = get_state_number("ei_withheld")
installments_paid = get_state_number("installments_paid")
other_payments = get_state_number("other_payments")
ontario_fertility_treatment_expenses = get_state_number("ontario_fertility_treatment_expenses")
ontario_seniors_public_transit_expenses = get_state_number("ontario_seniors_public_transit_expenses")
bc_renters_credit_eligible = get_state_bool("bc_renters_credit_eligible")
bc_home_renovation_expenses = get_state_number("bc_home_renovation_expenses")
bc_home_renovation_eligible = get_state_bool("bc_home_renovation_eligible")
sk_fertility_treatment_expenses = get_state_number("sk_fertility_treatment_expenses")
pe_volunteer_credit_eligible = get_state_bool("pe_volunteer_credit_eligible")
mb479_personal_tax_credit = get_state_number("mb479_personal_tax_credit")
mb479_homeowners_affordability_credit = get_state_number("mb479_homeowners_affordability_credit")
mb479_renters_affordability_credit = get_state_number("mb479_renters_affordability_credit")
mb479_seniors_school_rebate = get_state_number("mb479_seniors_school_rebate")
mb479_primary_caregiver_credit = get_state_number("mb479_primary_caregiver_credit")
mb479_fertility_treatment_expenses = get_state_number("mb479_fertility_treatment_expenses")
ns479_volunteer_credit = get_state_number("ns479_volunteer_credit")
ns479_childrens_sports_arts_credit = get_state_number("ns479_childrens_sports_arts_credit")
nb_political_contribution_credit = get_state_number("nb_political_contribution_credit")
nb_small_business_investor_credit = get_state_number("nb_small_business_investor_credit")
nb_lsvcc_credit = get_state_number("nb_lsvcc_credit")
nb_seniors_home_renovation_expenses = get_state_number("nb_seniors_home_renovation_expenses")
nl_political_contribution_credit = get_state_number("nl_political_contribution_credit")
nl_direct_equity_credit = get_state_number("nl_direct_equity_credit")
nl_resort_property_credit = get_state_number("nl_resort_property_credit")
nl_venture_capital_credit = get_state_number("nl_venture_capital_credit")
nl_unused_venture_capital_credit = get_state_number("nl_unused_venture_capital_credit")
nl479_other_refundable_credits = get_state_number("nl479_other_refundable_credits")

q_has_spouse_answer = "Yes" if bool(st.session_state.get("mvp_has_spouse_end_of_year", False)) else "No"
q_check_cwb_answer = "Yes" if bool(st.session_state.get("mvp_check_cwb", False)) else "No"
has_spouse_end_of_year_effective = bool(st.session_state.get("mvp_has_spouse_end_of_year", False))
spouse_claim_enabled_effective = has_spouse_end_of_year_effective and bool(st.session_state.get("mvp_spouse_claim_enabled", False))
spouse_net_income = float(st.session_state.get("mvp_spouse_net_income", spouse_net_income) or 0.0)
cwb_basic_eligible_effective = bool(st.session_state.get("mvp_check_cwb", False)) and bool(st.session_state.get("mvp_cwb_basic_eligible", False))
cwb_disability_supplement_eligible = bool(st.session_state.get("mvp_cwb_disability_supplement_eligible", cwb_disability_supplement_eligible))
spouse_cwb_disability_supplement_eligible = bool(
    st.session_state.get("mvp_spouse_cwb_disability_supplement_eligible", spouse_cwb_disability_supplement_eligible)
)

employment_income = employment_income_manual + float(t4_wizard_totals.get("box14_employment_income", 0.0))
pension_income = pension_income_manual + float(t4a_wizard_totals.get("box16_pension", 0.0)) + float(t3_wizard_totals.get("box31_pension_income", 0.0))
other_income = other_income_manual + rrsp_rrif_income_manual + float(t4a_wizard_totals.get("box18_lump_sum", 0.0)) + float(t4a_wizard_totals.get("box28_other_income", 0.0)) + float(t3_wizard_totals.get("box26_other_income", 0.0)) + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0))
net_rental_income = manual_net_rental_income + t776_net_rental_income
taxable_capital_gains = manual_taxable_capital_gains + schedule3_taxable_capital_gains
interest_income = interest_income_manual + float(t5_wizard_totals.get("box13_interest", 0.0))
t5_eligible_dividends_taxable += float(t5_wizard_totals.get("box25_eligible_dividends_taxable", 0.0)) + float(t4ps_wizard_totals.get("box31_eligible_dividends_taxable", 0.0))
t5_non_eligible_dividends_taxable += float(t5_wizard_totals.get("box11_non_eligible_dividends_taxable", 0.0)) + float(t4ps_wizard_totals.get("box25_non_eligible_dividends_taxable", 0.0))
federal_dividend_credit_slip_total = float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0)) + float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0)) + float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0)) + float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0)) + float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0)) + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0))
t5_federal_dividend_credit += float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0)) + float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0)) + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0)) + float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0))
t3_eligible_dividends_taxable += float(t3_wizard_totals.get("box50_eligible_dividends_taxable", 0.0))
t3_non_eligible_dividends_taxable += float(t3_wizard_totals.get("box32_non_eligible_dividends_taxable", 0.0))
t3_federal_dividend_credit += float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0)) + float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0))
t4_reference_box24_total = float(t4_wizard_totals.get("box24_ei_insurable_earnings", 0.0))
t4_reference_box26_total = float(t4_wizard_totals.get("box26_cpp_pensionable_earnings", 0.0))
t4_reference_box52_total = float(t4_wizard_totals.get("box52_pension_adjustment", 0.0))

tuition_cf_df = coerce_editor_df(pd.DataFrame(columns=["tax_year", "available_amount", "claim_amount"]), ["tax_year", "available_amount", "claim_amount"])
donation_cf_df = coerce_editor_df(pd.DataFrame(columns=["tax_year", "available_amount", "claim_amount"]), ["tax_year", "available_amount", "claim_amount"])
provincial_credit_lines_df = coerce_editor_df(pd.DataFrame(columns=["line_code", "amount"]), ["line_code", "amount"])
tuition_carryforward_available_total = 0.0
tuition_carryforward_claim_requested = 0.0
tuition_carryforward_claim_total = 0.0
tuition_carryforward_unused = 0.0
donation_carryforward_available_total = 0.0
donation_carryforward_claim_requested = 0.0
donation_carryforward_claim_total = 0.0
donation_carryforward_unused = 0.0
provincial_credit_lines_total = 0.0
schedule11_current_year_tuition_available = t2202_tuition_total
schedule11_current_year_claim_requested = schedule11_current_year_tuition_available if tuition_amount_claim == 0.0 else tuition_amount_claim
schedule11_current_year_claim_used = min(schedule11_current_year_tuition_available, schedule11_current_year_claim_requested)
schedule9_current_year_donations_available = max(donations_eligible_total, charitable_donations)
schedule9_current_year_donations_claim_requested = schedule9_current_year_donations_available
schedule9_current_year_donations_claim_used = 0.0
schedule9_current_year_donations_unused = schedule9_current_year_donations_available
schedule9_total_regular_donations_claimed = 0.0
schedule9_total_regular_donations_unused = schedule9_current_year_donations_available
income_tax_withheld_total = income_tax_withheld + float(t4_wizard_totals.get("box22_tax_withheld", 0.0)) + float(t4a_wizard_totals.get("box22_tax_withheld", 0.0))
cpp_withheld_total = cpp_withheld + float(t4_wizard_totals.get("box16_cpp", 0.0))
ei_withheld_total = ei_withheld + float(t4_wizard_totals.get("box18_ei", 0.0))
refundable_credits_engine_total = canada_workers_benefit + canada_training_credit + medical_expense_supplement + other_federal_refundable_credits + manual_provincial_refundable_credits + refundable_credits

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
if cwb_basic_eligible_effective:
    auto_canada_workers_benefit_preview = calculate_canada_workers_benefit(
        tax_year=tax_year,
        working_income=employment_income,
        adjusted_net_income=estimated_adjusted_net_income_for_cwb,
        spouse_adjusted_net_income=estimated_spouse_adjusted_net_income_for_cwb,
        has_spouse=has_spouse_end_of_year_effective,
    )
    auto_cwb_disability_supplement_preview = calculate_cwb_disability_supplement(
        tax_year=tax_year,
        adjusted_net_income=estimated_adjusted_net_income_for_cwb,
        spouse_adjusted_net_income=estimated_spouse_adjusted_net_income_for_cwb,
        has_spouse=has_spouse_end_of_year_effective,
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
        "t2202_months_total": float(t2202_wizard_totals.get("box24_total_months_part_time", 0.0)) + float(t2202_wizard_totals.get("box25_total_months_full_time", 0.0)),
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

question_gating_items = [
    (get_state_text("q_has_rental_income") == "Yes" and get_state_number("net_rental_income") == 0.0),
    (get_state_text("q_has_capital_gains") == "Yes" and get_state_number("taxable_capital_gains") == 0.0),
    (get_state_text("q_has_other_income") == "Yes" and get_state_number("other_income") == 0.0),
    (get_state_text("q_has_rrsp") == "Yes" and get_state_number("rrsp_deduction") == 0.0),
    (get_state_text("q_has_fhsa") == "Yes" and get_state_number("fhsa_deduction") == 0.0),
    (get_state_text("q_has_child_care") == "Yes" and get_state_number("child_care_expenses") == 0.0),
    (get_state_text("q_has_moving") == "Yes" and get_state_number("moving_expenses") == 0.0),
    (get_state_text("q_has_work_expenses") == "Yes" and get_state_number("other_employment_expenses") == 0.0),
    (get_state_text("q_has_student_loan") == "Yes" and get_state_number("student_loan_interest") == 0.0),
    (get_state_text("q_has_medical") == "Yes" and get_state_number("medical_expenses_paid") == 0.0),
    (get_state_text("q_has_donations") == "Yes" and get_state_number("charitable_donations") == 0.0),
    (get_state_text("q_has_spouse") == "Yes" and get_state_number("spouse_net_income") == 0.0),
    (get_state_text("q_has_dependant") == "Yes" and get_state_number("eligible_dependant_net_income") == 0.0),
    (get_state_text("q_has_payments") == "Yes" and get_state_number("installments_paid") == 0.0 and get_state_number("other_payments") == 0.0),
]
questions_incomplete = any(question_gating_items)

if mvp_step == "questions":
    st.info("Check any items above that relate to you before continuing.")
    render_mvp_step_footer(
        "questions",
        next_disabled=questions_incomplete,
        helper_text="If you answered Yes to an item above, add the related amount before continuing.",
    )

calculate_clicked = False
if mvp_step == "review_return":
    render_step_heading("4. Review Return", "4-review-return")
    slips_used_rows = pd.DataFrame(
        [
            {"Slip": "T4 slips", "Count": len(t4_wizard_records), "Key amount": format_currency(float(t4_wizard_totals.get("box14_employment_income", 0.0)))},
            {"Slip": "T4A slips", "Count": len(t4a_wizard_records), "Key amount": format_currency(float(t4a_wizard_totals.get("box048_fees_other_services", 0.0)))},
            {"Slip": "T5 slips", "Count": len(t5_wizard_records), "Key amount": format_currency(float(t5_wizard_totals.get("box13_interest", 0.0)))},
            {"Slip": "T3 slips", "Count": len(t3_wizard_records), "Key amount": format_currency(float(t3_wizard_totals.get("box26_other_income", 0.0)))},
            {"Slip": "T4PS slips", "Count": len(t4ps_wizard_records), "Key amount": format_currency(float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0)))},
            {"Slip": "T2202 forms", "Count": len(t2202_wizard_records), "Key amount": format_currency(t2202_tuition_total)},
        ]
    )
    slips_used_rows = slips_used_rows[slips_used_rows["Count"] > 0]
    with st.container(border=True):
        st.markdown("#### Slips Used")
        if slips_used_rows.empty:
            st.caption("No supported slips are currently loaded in this review.")
        else:
            st.dataframe(slips_used_rows, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("#### Extra Amounts Added")
        st.dataframe(
            build_currency_df(
                [
                    {"Item": "Net rental income", "Amount": net_rental_income},
                    {"Item": "Taxable capital gains", "Amount": taxable_capital_gains},
                    {"Item": "Other taxable income", "Amount": other_income},
                    {"Item": "RRSP deduction", "Amount": rrsp_deduction},
                    {"Item": "FHSA deduction", "Amount": fhsa_deduction},
                    {"Item": "Work expenses", "Amount": other_employment_expenses},
                    {"Item": "Medical expenses paid", "Amount": medical_expenses_paid},
                    {"Item": "Charitable donations", "Amount": charitable_donations},
                    {"Item": "Tax instalments paid", "Amount": installments_paid},
                    {"Item": "Other tax payments / credits", "Amount": other_payments},
                ],
                ["Amount"],
            ),
            use_container_width=True,
            hide_index=True,
        )

    with st.container(border=True):
        st.markdown("#### Household And Benefits Elections")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Item": "Spouse or common-law partner at year end", "Status": "Yes" if has_spouse_end_of_year_effective else "No"},
                    {"Item": "Check spouse amount eligibility", "Status": "Yes" if spouse_claim_enabled_effective else "No"},
                    {"Item": "Spouse net income entered", "Status": format_currency(spouse_net_income) if has_spouse_end_of_year_effective else "Not entered"},
                    {"Item": "Check eligible dependant amount", "Status": "Yes" if eligible_dependant_claim_enabled else "No"},
                    {"Item": "Check Canada Workers Benefit (CWB)", "Status": "Yes" if cwb_basic_eligible_effective else "No"},
                    {"Item": "Check CWB disability supplement", "Status": "Yes" if cwb_disability_supplement_eligible else "No"},
                    {"Item": "Check spouse CWB disability supplement", "Status": "Yes" if spouse_cwb_disability_supplement_eligible else "No"},
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    if debug_mode:
        with st.expander("MVP Debug: spouse and CWB inputs", expanded=True):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Field": "q_has_spouse", "Value": get_state_text("q_has_spouse")},
                        {"Field": "mvp_has_spouse_end_of_year", "Value": st.session_state.get("mvp_has_spouse_end_of_year", False)},
                        {"Field": "has_spouse_end_of_year", "Value": has_spouse_end_of_year},
                        {"Field": "has_spouse_end_of_year_effective", "Value": has_spouse_end_of_year_effective},
                        {"Field": "spouse_claim_enabled", "Value": spouse_claim_enabled},
                        {"Field": "mvp_spouse_claim_enabled", "Value": st.session_state.get("mvp_spouse_claim_enabled", False)},
                        {"Field": "spouse_claim_enabled_effective", "Value": spouse_claim_enabled_effective},
                        {"Field": "spouse_net_income", "Value": spouse_net_income},
                        {"Field": "mvp_spouse_net_income", "Value": st.session_state.get("mvp_spouse_net_income", 0.0)},
                        {"Field": "separated_in_year", "Value": separated_in_year},
                        {"Field": "support_payments_to_spouse", "Value": support_payments_to_spouse},
                        {"Field": "q_check_cwb", "Value": get_state_text("q_check_cwb")},
                        {"Field": "mvp_check_cwb", "Value": st.session_state.get("mvp_check_cwb", False)},
                        {"Field": "cwb_basic_eligible", "Value": cwb_basic_eligible},
                        {"Field": "mvp_cwb_basic_eligible", "Value": st.session_state.get("mvp_cwb_basic_eligible", False)},
                        {"Field": "cwb_basic_eligible_effective", "Value": cwb_basic_eligible_effective},
                        {"Field": "cwb_disability_supplement_eligible", "Value": cwb_disability_supplement_eligible},
                        {"Field": "spouse_cwb_disability_supplement_eligible", "Value": spouse_cwb_disability_supplement_eligible},
                        {"Field": "estimated_adjusted_net_income_for_cwb", "Value": estimated_adjusted_net_income_for_cwb},
                        {"Field": "estimated_spouse_adjusted_net_income_for_cwb", "Value": estimated_spouse_adjusted_net_income_for_cwb},
                        {"Field": "auto_canada_workers_benefit_preview", "Value": auto_canada_workers_benefit_preview["credit"]},
                        {"Field": "auto_cwb_disability_supplement_preview", "Value": auto_cwb_disability_supplement_preview["credit"]},
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

    if diagnostics:
        with st.expander("Review Flags", expanded=True):
            render_diagnostics_panel(diagnostics, formatter=format_plain_number)
    else:
        st.info("No obvious duplication or consistency issues were detected from the current inputs.")

    st.info("Review the summary above before clicking Calculate.")
    action_col1, action_col2 = st.columns([1.2, 4.8])
    with action_col1:
        calculate_clicked = st.button("Calculate", type="primary", use_container_width=True)
    render_mvp_step_footer(
        "review_return",
        show_next=False,
        helper_text="Review the summary above, then click Calculate Return to continue to Results.",
    )

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
            "spouse_amount_claim": spouse_amount_claim,
            "spouse_net_income": spouse_net_income,
            "spouse_claim_enabled": spouse_claim_enabled_effective,
            "spouse_infirm": spouse_infirm,
            "has_spouse_end_of_year": has_spouse_end_of_year_effective,
            "separated_in_year": separated_in_year,
            "support_payments_to_spouse": support_payments_to_spouse,
            "eligible_dependant_claim": eligible_dependant_claim,
            "eligible_dependant_net_income": eligible_dependant_net_income,
            "eligible_dependant_claim_enabled": eligible_dependant_claim_enabled,
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
            "canada_workers_benefit": canada_workers_benefit,
            "cwb_basic_eligible": cwb_basic_eligible_effective,
            "cwb_disability_supplement_eligible": cwb_disability_supplement_eligible,
            "spouse_cwb_disability_supplement_eligible": spouse_cwb_disability_supplement_eligible,
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
    st.session_state["mvp_step"] = "results"
    queue_step_scroll("results")
    st.rerun()

if mvp_step == "results" and "tax_result" not in st.session_state:
    st.subheader("5. Results")
    st.info("No current result yet. Use the Review step to calculate the return first.")

if (
    mvp_step == "results"
    and "tax_result" in st.session_state
    and st.session_state.get("tax_result_input_signature") == current_input_signature
):
    result = st.session_state["tax_result"]
    postcalc_diagnostics = collect_postcalc_diagnostics(result)

    render_step_heading("6) Results", "6-results")
    provincial_form_code = PROVINCIAL_FORM_CODES.get(province, "428")
    tab_names, special_tab_name = build_results_tab_names()
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
        if debug_mode:
            with st.expander("MVP Debug: spouse and CWB results", expanded=True):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Field": "line_30300_effective_spouse_claim", "Value": result.get("effective_spouse_claim", 0.0)},
                            {"Field": "auto_spouse_amount", "Value": result.get("auto_spouse_amount", 0.0)},
                            {"Field": "household_spouse_allowed", "Value": result.get("household_spouse_allowed", 0.0)},
                            {"Field": "household_spouse_reason", "Value": result.get("household_spouse_reason", "")},
                            {"Field": "line_45300_canada_workers_benefit", "Value": result.get("canada_workers_benefit", 0.0)},
                            {"Field": "cwb_basic_eligible", "Value": result.get("cwb_basic_eligible", 0.0)},
                            {"Field": "canada_workers_benefit_preview", "Value": result.get("canada_workers_benefit_preview", 0.0)},
                            {"Field": "canada_workers_benefit_auto", "Value": result.get("canada_workers_benefit_auto", 0.0)},
                            {"Field": "canada_workers_benefit_manual", "Value": result.get("canada_workers_benefit_manual", 0.0)},
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
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
        summary_suggestions = build_results_summary_suggestions(
            session_state=st.session_state,
            result=result,
            readiness_df=readiness_df,
            tax_year=tax_year,
            province=province,
            province_name=province_name,
            age=age,
        )
        product_recommendation_cards = build_productized_recommendation_cards(
            result=result,
            has_spouse=has_spouse_end_of_year_effective,
            spouse_claim_enabled=spouse_claim_enabled_effective,
            spouse_net_income=spouse_net_income,
            cwb_checked=(q_check_cwb_answer == "Yes"),
            cwb_effective=cwb_basic_eligible_effective,
            paid_rent_or_property_tax=(get_state_number("t776_property_taxes") > 0.0),
            has_dependants=(get_state_text("q_has_dependant") == "Yes"),
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
            product_cards=product_recommendation_cards,
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
                "Download Ontario Summary (PDF)",
                data=printable_pdf,
                file_name="ontario-tax-estimate-summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        st.caption("Simpler summary for sharing. This PDF is an estimate summary, not a filed return or CRA-certified filing package.")
        st.caption("If you want a second review of slips, support, or filing readiness, reach out: info@contexta.biz")

    with return_tab:
        st.caption("Ontario worksheet view for estimate review. Open the line details only if you want a deeper manual check.")

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
        st.markdown("#### Advanced Review Checks")
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
                "Download Ontario Report Pack (PDF)",
                data=report_pack_pdf,
                file_name="ontario-tax-estimate-report-pack.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.caption("This report pack is for review support only. It is not a CRA-certified filing package and may still require manual checks.")

    with t2209_tab:
        st.markdown("#### Ontario Foreign Tax Credit Worksheet")
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
        st.markdown("#### Ontario Worksheet View")
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
        st.markdown("#### Ontario Rental Worksheet (T776)")
        t776_rows = build_t776_df(result)
        t776_rows["Amount"] = t776_rows["Amount"].map(format_currency)
        with st.expander("Detailed T776 Lines", expanded=False):
            st.dataframe(t776_rows, use_container_width=True, hide_index=True)

    with s3_tab:
        st.markdown("#### Ontario Capital Gains Worksheet (Schedule 3)")
        s3_rows = build_schedule_3_df(result)
        s3_rows["Amount"] = s3_rows["Amount"].map(format_currency)
        with st.expander("Detailed Schedule 3 Lines", expanded=False):
            st.dataframe(s3_rows, use_container_width=True, hide_index=True)

    with s11_tab:
        st.markdown("#### Ontario Tuition Worksheet (Schedule 11)")
        st.caption("Training credit is applied first, then carryforward, then line 32300.")
        s11_rows = build_schedule_11_df(result)
        s11_rows["Amount"] = s11_rows["Amount"].map(format_currency)
        with st.expander("Detailed Schedule 11 Lines", expanded=False):
            st.dataframe(s11_rows, use_container_width=True, hide_index=True)

    with s9_tab:
        st.markdown("#### Ontario Donations Worksheet (Schedule 9)")
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
        st.warning(
            "This tool provides an Ontario-focused estimate and review workflow. It is not CRA-certified filing software, and some benefits or complex cases still require separate review."
        )
        with st.expander("Supported Scope", expanded=False):
            st.markdown(read_public_markdown_doc("PUBLIC_SUPPORTED_SCOPE.md"))
        with st.expander("Best-Fit And Review Scenarios", expanded=False):
            st.markdown(read_public_markdown_doc("PUBLIC_BEST_FIT_AND_REVIEW_SCENARIOS.md"))
        with st.expander("Limitations And Boundaries", expanded=False):
            st.markdown(read_public_markdown_doc("PUBLIC_LIMITATIONS.md"))
        st.caption("Before filing, manually review any unsupported slips, low-confidence extractions, carryforwards, separately reviewed benefits, and unusual household situations.")

    if special_tab is not None:
        with special_tab:
            st.markdown(f"#### {special_tab_name} Worksheet View")
            special_rows = build_special_schedule_df(result, province)
            if special_rows.empty:
                st.caption("No additional province-specific rows are available for this province yet.")
            else:
                special_rows["Amount"] = special_rows["Amount"].map(format_currency)
                st.dataframe(special_rows, use_container_width=True, hide_index=True)
    render_mvp_step_footer(
        "results",
        show_next=False,
        show_reset=True,
        helper_text="Use Back to return to earlier steps and make adjustments.",
    )

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
render_pending_step_scroll()
st.caption(
    "This tool helps extract data from uploaded slips and estimate an Ontario personal T1 result, but it does not replace CRA-certified filing software. "
    "Always manually review imported amounts, unsupported slips, carryforwards, separately reviewed benefits, and unusual household or credit situations before filing."
)
debug_mode = st.toggle(
    "Developer mode",
    value=debug_mode,
    key="debug_mode",
    help="Show internal debug panels for MVP flow troubleshooting.",
)
