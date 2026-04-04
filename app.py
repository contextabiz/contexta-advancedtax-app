import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from tax_config import AVAILABLE_PROVINCES, AVAILABLE_TAX_YEARS, PROVINCES, TAX_CONFIGS
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
APP_URL = "https://tax.contexta.biz/"
OG_IMAGE_URL = "https://tax.contexta.biz/canadian-income-tax-estimator-og.jpg"
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
PROVINCIAL_CAREGIVER_HELP = {
    "AB": "AB428 caregiver amount base. Alberta's 2025 maximum is $12,922 per dependant before applying the 6% credit rate.",
    "NB": "NB428 caregiver amount base. New Brunswick's 2025 infirm dependant amount is up to $5,839 before applying the 9.4% credit rate.",
    "NL": "NL428 caregiver/infirm dependant base. Enter the eligible base amount from your worksheet if applicable.",
    "NS": "NS428 caregiver amount base. Enter the eligible amount from your worksheet if applicable.",
    "ON": "Ontario caregiver claim amount base if applicable.",
    "PE": "PE428 infirm dependant amount base. Prince Edward Island's 2025 amount is up to $2,446 before the provincial credit rate.",
    "SK": "SK428 caregiver amount base. Saskatchewan's 2025 maximum is $13,986 per dependant before the 10.5% credit rate.",
}
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
            {"id": "box14_employment_income", "label": "Please fill Box 14 Employment Income", "step": 100.0},
            {"id": "box22_tax_withheld", "label": "Please fill Box 22 Income Tax Deducted", "step": 100.0},
            {"id": "box16_cpp", "label": "Please fill Box 16 CPP Contributions", "step": 10.0},
            {"id": "box18_ei", "label": "Please fill Box 18 EI Premiums", "step": 10.0},
            {"id": "box24_ei_insurable_earnings", "label": "Please fill Box 24 EI Insurable Earnings", "step": 100.0},
            {"id": "box26_cpp_pensionable_earnings", "label": "Please fill Box 26 CPP/QPP Pensionable Earnings", "step": 100.0},
            {"id": "box20_rpp", "label": "Please fill Box 20 RPP Contributions", "step": 10.0},
            {"id": "box52_pension_adjustment", "label": "Please fill Box 52 Pension Adjustment", "step": 10.0},
            {"id": "box44_union_dues", "label": "Please fill Box 44 Union Dues", "step": 10.0},
        ],
    },
    {
        "tab": "T4A",
        "title": "T4A Slip",
        "key": "t4a_wizard",
        "columns": ["box16_pension", "box18_lump_sum", "box22_tax_withheld", "box28_other_income"],
        "fields": [
            {"id": "box16_pension", "label": "Please fill Box 16 Pension or Superannuation", "step": 100.0},
            {"id": "box18_lump_sum", "label": "Please fill Box 18 Lump-Sum Payment", "step": 100.0},
            {"id": "box22_tax_withheld", "label": "Please fill Box 22 Income Tax Deducted", "step": 100.0},
            {"id": "box28_other_income", "label": "Please fill Box 28 Other Income", "step": 100.0},
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
            {"id": "box13_interest", "label": "Please fill Box 13 Interest from Canadian Sources", "step": 10.0},
            {"id": "box15_foreign_income", "label": "Please fill Box 15 Foreign Income", "step": 10.0},
            {"id": "box16_foreign_tax_paid", "label": "Please fill Box 16 Foreign Tax Paid", "step": 10.0},
            {"id": "box25_eligible_dividends_taxable", "label": "Please fill Box 25 Taxable Amount of Eligible Dividends", "step": 10.0},
            {"id": "box26_eligible_dividend_credit", "label": "Please fill Box 26 Dividend Tax Credit for Eligible Dividends", "step": 10.0},
            {"id": "box11_non_eligible_dividends_taxable", "label": "Please fill Box 11 Taxable Amount of Other Than Eligible Dividends", "step": 10.0},
            {"id": "box12_non_eligible_dividend_credit", "label": "Please fill Box 12 Dividend Tax Credit for Other Than Eligible Dividends", "step": 10.0},
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
            {"id": "box21_capital_gains", "label": "Please fill Box 21 Capital Gains", "step": 10.0},
            {"id": "box31_pension_income", "label": "Please fill Box 31 Pension Income", "step": 10.0},
            {"id": "box26_other_income", "label": "Please fill Box 26 Other Income", "step": 10.0},
            {"id": "box25_foreign_income", "label": "Please fill Box 25 Foreign Non-Business Income", "step": 10.0},
            {"id": "box34_foreign_tax_paid", "label": "Please fill Box 34 Foreign Non-Business Tax Paid", "step": 10.0},
            {"id": "box50_eligible_dividends_taxable", "label": "Please fill Box 50 Taxable Amount of Eligible Dividends", "step": 10.0},
            {"id": "box51_eligible_dividend_credit", "label": "Please fill Box 51 Dividend Tax Credit for Eligible Dividends", "step": 10.0},
            {"id": "box32_non_eligible_dividends_taxable", "label": "Please fill Box 32 Taxable Amount of Other Than Eligible Dividends", "step": 10.0},
            {"id": "box39_non_eligible_dividend_credit", "label": "Please fill Box 39 Dividend Tax Credit for Other Than Eligible Dividends", "step": 10.0},
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
            {"id": "box24_non_eligible_dividends_actual", "label": "Please fill Box 24 Actual Amount of Non-Eligible Dividends", "step": 10.0},
            {"id": "box25_non_eligible_dividends_taxable", "label": "Please fill Box 25 Taxable Amount of Non-Eligible Dividends", "step": 10.0},
            {"id": "box26_non_eligible_dividend_credit", "label": "Please fill Box 26 Dividend Tax Credit for Non-Eligible Dividends", "step": 10.0},
            {"id": "box30_eligible_dividends_actual", "label": "Please fill Box 30 Actual Amount of Eligible Dividends", "step": 10.0},
            {"id": "box31_eligible_dividends_taxable", "label": "Please fill Box 31 Taxable Amount of Eligible Dividends", "step": 10.0},
            {"id": "box32_eligible_dividend_credit", "label": "Please fill Box 32 Dividend Tax Credit for Eligible Dividends", "step": 10.0},
            {"id": "box34_capital_gains_or_losses", "label": "Please fill Box 34 Capital Gains or Losses", "step": 10.0},
            {"id": "box35_other_employment_income", "label": "Please fill Box 35 Other Employment Income", "step": 10.0},
            {"id": "box37_foreign_non_business_income", "label": "Please fill Box 37 Foreign Non-Business Income", "step": 10.0},
            {"id": "box41_epsp_contributions", "label": "Please fill Box 41 EPSP Contributions (Reference)", "step": 10.0},
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
            {"id": "box21_months_part_time", "label": "Please fill Box 21 Eligible Months Part-Time", "step": 1.0},
            {"id": "box22_months_full_time", "label": "Please fill Box 22 Eligible Months Full-Time", "step": 1.0},
            {"id": "box23_session_tuition", "label": "Please fill Box 23 Tuition Fees for This Session", "step": 10.0},
            {"id": "box24_total_months_part_time", "label": "Please fill Box 24 Total Months Part-Time", "step": 1.0},
            {"id": "box25_total_months_full_time", "label": "Please fill Box 25 Total Months Full-Time", "step": 1.0},
            {"id": "box26_total_eligible_tuition", "label": "Please fill Box 26 Total Eligible Tuition Fees", "step": 10.0},
        ],
    },
]


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


def build_return_package_df(result: dict, province_name: str) -> pd.DataFrame:
    return build_currency_df(
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
        float(t5_wizard_totals.get("box25_taxable_eligible_dividends", 0.0))
        + float(t3_wizard_totals.get("box50_taxable_eligible_dividends", 0.0))
        + float(t4ps_wizard_totals.get("box31_taxable_eligible_dividends", 0.0))
    )
    non_eligible_dividend_slip_total = (
        float(t5_wizard_totals.get("box11_taxable_non_eligible_dividends", 0.0))
        + float(t3_wizard_totals.get("box32_taxable_non_eligible_dividends", 0.0))
        + float(t4ps_wizard_totals.get("box25_taxable_non_eligible_dividends", 0.0))
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

    rows = [
        {
            "Group": "Income",
            "Area": "Employment",
            "Slip Total": float(t4_wizard_totals.get("box14_employment_income", 0.0)),
            "Manual / Extra Input": employment_income_manual,
            "Return Amount Used": result.get("line_10100", 0.0),
            "Difference": result.get("line_10100", 0.0) - (float(t4_wizard_totals.get("box14_employment_income", 0.0)) + employment_income_manual),
        },
        {
            "Group": "Income",
            "Area": "Pension",
            "Slip Total": float(t4a_wizard_totals.get("box16_pension", 0.0)) + float(t3_wizard_totals.get("box31_pension_income", 0.0)),
            "Manual / Extra Input": pension_income_manual,
            "Return Amount Used": result.get("line_pension_income", 0.0),
            "Difference": result.get("line_pension_income", 0.0) - (
                float(t4a_wizard_totals.get("box16_pension", 0.0)) + float(t3_wizard_totals.get("box31_pension_income", 0.0)) + pension_income_manual
            ),
        },
        {
            "Group": "Income",
            "Area": "Other income",
            "Slip Total": float(t4a_wizard_totals.get("box18_lump_sum", 0.0)) + float(t4a_wizard_totals.get("box28_other_income", 0.0)) + float(t3_wizard_totals.get("box26_other_income", 0.0)) + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0)),
            "Manual / Extra Input": other_income_manual,
            "Return Amount Used": result.get("line_other_income", 0.0),
            "Difference": result.get("line_other_income", 0.0) - (
                float(t4a_wizard_totals.get("box18_lump_sum", 0.0))
                + float(t4a_wizard_totals.get("box28_other_income", 0.0))
                + float(t3_wizard_totals.get("box26_other_income", 0.0))
                + float(t4ps_wizard_totals.get("box35_other_employment_income", 0.0))
                + other_income_manual
            ),
        },
        {
            "Group": "Income",
            "Area": "Interest",
            "Slip Total": float(t5_wizard_totals.get("box13_interest", 0.0)),
            "Manual / Extra Input": interest_income_manual,
            "Return Amount Used": result.get("line_interest_income", 0.0),
            "Difference": result.get("line_interest_income", 0.0) - (float(t5_wizard_totals.get("box13_interest", 0.0)) + interest_income_manual),
        },
        {
            "Group": "Income",
            "Area": "Eligible dividends",
            "Slip Total": eligible_dividend_slip_total,
            "Manual / Extra Input": clip_non_negative(result.get("taxable_eligible_dividends", 0.0) - eligible_dividend_slip_total),
            "Return Amount Used": result.get("taxable_eligible_dividends", 0.0),
            "Difference": result.get("taxable_eligible_dividends", 0.0) - (
                eligible_dividend_slip_total
                + clip_non_negative(result.get("taxable_eligible_dividends", 0.0) - eligible_dividend_slip_total)
            ),
        },
        {
            "Group": "Income",
            "Area": "Non-eligible dividends",
            "Slip Total": non_eligible_dividend_slip_total,
            "Manual / Extra Input": clip_non_negative(result.get("taxable_non_eligible_dividends", 0.0) - non_eligible_dividend_slip_total),
            "Return Amount Used": result.get("taxable_non_eligible_dividends", 0.0),
            "Difference": result.get("taxable_non_eligible_dividends", 0.0) - (
                non_eligible_dividend_slip_total
                + clip_non_negative(result.get("taxable_non_eligible_dividends", 0.0) - non_eligible_dividend_slip_total)
            ),
        },
        {
            "Group": "Credits",
            "Area": "Foreign income",
            "Slip Total": foreign_income_slip_total,
            "Manual / Extra Input": clip_non_negative(result.get("t2209_net_foreign_non_business_income", 0.0) - foreign_income_slip_total),
            "Return Amount Used": result.get("t2209_net_foreign_non_business_income", 0.0),
            "Difference": result.get("t2209_net_foreign_non_business_income", 0.0) - (
                foreign_income_slip_total
                + clip_non_negative(result.get("t2209_net_foreign_non_business_income", 0.0) - foreign_income_slip_total)
            ),
        },
        {
            "Group": "Credits",
            "Area": "Foreign tax paid",
            "Slip Total": foreign_tax_slip_total,
            "Manual / Extra Input": clip_non_negative(result.get("t2209_non_business_tax_paid", 0.0) - foreign_tax_slip_total),
            "Return Amount Used": result.get("t2209_non_business_tax_paid", 0.0),
            "Difference": result.get("t2209_non_business_tax_paid", 0.0) - (
                foreign_tax_slip_total
                + clip_non_negative(result.get("t2209_non_business_tax_paid", 0.0) - foreign_tax_slip_total)
            ),
        },
        {
            "Group": "Payments",
            "Area": "Tax withheld",
            "Slip Total": float(t4_wizard_totals.get("box22_tax_withheld", 0.0)) + float(t4a_wizard_totals.get("box22_tax_withheld", 0.0)),
            "Manual / Extra Input": max(0.0, result.get("income_tax_withheld", 0.0) - float(t4_wizard_totals.get("box22_tax_withheld", 0.0)) - float(t4a_wizard_totals.get("box22_tax_withheld", 0.0))),
            "Return Amount Used": result.get("income_tax_withheld", 0.0),
            "Difference": 0.0,
        },
        {
            "Group": "Payments",
            "Area": "CPP withheld",
            "Slip Total": float(t4_wizard_totals.get("box16_cpp", 0.0)),
            "Manual / Extra Input": max(0.0, result.get("cpp_withheld_total", 0.0) - float(t4_wizard_totals.get("box16_cpp", 0.0))),
            "Return Amount Used": result.get("cpp_withheld_total", 0.0),
            "Difference": result.get("cpp_withheld_total", 0.0) - float(t4_wizard_totals.get("box16_cpp", 0.0)) - max(0.0, result.get("cpp_withheld_total", 0.0) - float(t4_wizard_totals.get("box16_cpp", 0.0))),
        },
        {
            "Group": "Payments",
            "Area": "EI withheld",
            "Slip Total": float(t4_wizard_totals.get("box18_ei", 0.0)),
            "Manual / Extra Input": max(0.0, result.get("ei_withheld_total", 0.0) - float(t4_wizard_totals.get("box18_ei", 0.0))),
            "Return Amount Used": result.get("ei_withheld_total", 0.0),
            "Difference": result.get("ei_withheld_total", 0.0) - float(t4_wizard_totals.get("box18_ei", 0.0)) - max(0.0, result.get("ei_withheld_total", 0.0) - float(t4_wizard_totals.get("box18_ei", 0.0))),
        },
        {
            "Group": "Credits",
            "Area": "Tuition",
            "Slip Total": max(float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)), float(t2202_wizard_totals.get("box23_session_tuition", 0.0))),
            "Manual / Extra Input": tuition_override,
            "Return Amount Used": result.get("schedule11_current_year_claim_used", 0.0),
            "Difference": result.get("schedule11_current_year_claim_used", 0.0) - (
                max(float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)), float(t2202_wizard_totals.get("box23_session_tuition", 0.0)))
                + tuition_override
            ),
        },
        {
            "Group": "Carryforwards",
            "Area": "Tuition carryforward",
            "Slip Total": result.get("schedule11_carryforward_available", 0.0),
            "Manual / Extra Input": result.get("schedule11_carryforward_claim_requested", 0.0),
            "Return Amount Used": result.get("schedule11_carryforward_claim_used", 0.0),
            "Difference": result.get("schedule11_carryforward_claim_used", 0.0) - min(
                result.get("schedule11_carryforward_available", 0.0),
                result.get("schedule11_carryforward_claim_requested", 0.0),
            ),
        },
        {
            "Group": "Credits",
            "Area": "Current-year donations",
            "Slip Total": result.get("schedule9_current_year_donations_available", 0.0),
            "Manual / Extra Input": max(
                0.0,
                result.get("federal_dividend_tax_credit", 0.0) - (
                    float(t5_wizard_totals.get("box26_eligible_dividend_tax_credit", 0.0))
                    + float(t5_wizard_totals.get("box12_non_eligible_dividend_tax_credit", 0.0))
                    + float(t3_wizard_totals.get("box51_eligible_dividend_tax_credit", 0.0))
                    + float(t3_wizard_totals.get("box39_non_eligible_dividend_tax_credit", 0.0))
                    + float(t4ps_wizard_totals.get("box32_eligible_dividend_tax_credit", 0.0))
                    + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0))
                ),
            ),
            "Return Amount Used": result.get("schedule9_current_year_donations_claim_used", 0.0),
            "Difference": result.get("schedule9_current_year_donations_claim_used", 0.0) - result.get("schedule9_current_year_donations_available", 0.0),
        },
        {
            "Group": "Carryforwards",
            "Area": "Donation carryforward",
            "Slip Total": result.get("schedule9_carryforward_available", 0.0),
            "Manual / Extra Input": result.get("schedule9_carryforward_claim_requested", 0.0),
            "Return Amount Used": result.get("schedule9_carryforward_claim_used", 0.0),
            "Difference": result.get("schedule9_carryforward_claim_used", 0.0) - min(
                result.get("schedule9_carryforward_available", 0.0),
                result.get("schedule9_carryforward_claim_requested", 0.0),
            ),
        },
        {
            "Group": "Carryforwards",
            "Area": "Capital loss carryforward",
            "Slip Total": result.get("net_capital_loss_carryforward_requested", 0.0),
            "Manual / Extra Input": result.get("line_taxable_capital_gains", 0.0),
            "Return Amount Used": result.get("net_capital_loss_carryforward", 0.0),
            "Difference": result.get("net_capital_loss_carryforward", 0.0) - min(
                result.get("net_capital_loss_carryforward_requested", 0.0),
                result.get("line_taxable_capital_gains", 0.0),
            ),
        },
        {
            "Group": "Credits",
            "Area": "Refundable credits",
            "Slip Total": result.get("federal_refundable_credits", 0.0) + result.get("provincial_special_refundable_credits", 0.0),
            "Manual / Extra Input": result.get("manual_provincial_refundable_credits", 0.0) + result.get("other_manual_refundable_credits", 0.0),
            "Return Amount Used": result.get("refundable_credits", 0.0),
            "Difference": result.get("refundable_credits", 0.0) - (
                result.get("federal_refundable_credits", 0.0)
                + result.get("provincial_special_refundable_credits", 0.0)
                + result.get("manual_provincial_refundable_credits", 0.0)
                + result.get("other_manual_refundable_credits", 0.0)
            ),
        },
        {
            "Group": "Credits",
            "Area": "Federal dividend tax credit",
            "Slip Total": float(t5_wizard_totals.get("box26_eligible_dividend_tax_credit", 0.0))
            + float(t5_wizard_totals.get("box12_non_eligible_dividend_tax_credit", 0.0))
            + float(t3_wizard_totals.get("box51_eligible_dividend_tax_credit", 0.0))
            + float(t3_wizard_totals.get("box39_non_eligible_dividend_tax_credit", 0.0))
            + float(t4ps_wizard_totals.get("box32_eligible_dividend_tax_credit", 0.0))
            + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_tax_credit", 0.0)),
            "Manual / Extra Input": 0.0,
            "Return Amount Used": result.get("federal_dividend_tax_credit", 0.0),
            "Difference": result.get("federal_dividend_tax_credit", 0.0) - (
                float(t5_wizard_totals.get("box26_eligible_dividend_tax_credit", 0.0))
                + float(t5_wizard_totals.get("box12_non_eligible_dividend_tax_credit", 0.0))
                + float(t3_wizard_totals.get("box51_eligible_dividend_tax_credit", 0.0))
                + float(t3_wizard_totals.get("box39_non_eligible_dividend_tax_credit", 0.0))
                + float(t4ps_wizard_totals.get("box32_eligible_dividend_tax_credit", 0.0))
                + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_tax_credit", 0.0))
            ),
        },
        {
            "Group": "Credits",
            "Area": "Foreign tax credit claimed",
            "Slip Total": result.get("t2209_non_business_tax_paid", 0.0),
            "Manual / Extra Input": 0.0,
            "Return Amount Used": result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0),
            "Difference": (result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0)) - result.get("t2209_non_business_tax_paid", 0.0),
        },
        {
            "Group": "Credits",
            "Area": "Household claims",
            "Slip Total": result.get("manual_spouse_claim", 0.0) + result.get("manual_eligible_dependant_claim", 0.0),
            "Manual / Extra Input": result.get("auto_spouse_amount", 0.0) + result.get("auto_eligible_dependant_amount", 0.0),
            "Return Amount Used": result.get("effective_spouse_claim", 0.0) + result.get("effective_eligible_dependant_claim", 0.0) + result.get("provincial_caregiver_claim_amount", 0.0) + result.get("household_disability_transfer_used", 0.0),
            "Difference": (
                result.get("effective_spouse_claim", 0.0)
                + result.get("effective_eligible_dependant_claim", 0.0)
                + result.get("provincial_caregiver_claim_amount", 0.0)
                + result.get("household_disability_transfer_used", 0.0)
            ) - (
                result.get("manual_spouse_claim", 0.0)
                + result.get("manual_eligible_dependant_claim", 0.0)
                + result.get("auto_spouse_amount", 0.0)
                + result.get("auto_eligible_dependant_amount", 0.0)
            ),
        },
    ]
    for row in rows:
        if row["Area"] == "Federal dividend tax credit":
            row["Slip Total"] = federal_dividend_credit_slip_total
            row["Manual / Extra Input"] = max(
                0.0,
                float(result.get("federal_dividend_tax_credit", 0.0)) - federal_dividend_credit_slip_total,
            )
            row["Difference"] = float(result.get("federal_dividend_tax_credit", 0.0)) - federal_dividend_credit_slip_total
        classify_row(row)
        row["Explanation"] = build_explanation(row)
    return build_currency_df(rows, ["Slip Total", "Manual / Extra Input", "Return Amount Used", "Difference"])


def build_assumptions_overrides_df(
    result: dict,
    province_name: str,
    tuition_claim_override: float,
    t2209_net_income_override: float,
    t2209_basic_federal_tax_override: float,
    t2036_provincial_tax_otherwise_payable_override: float,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(area: str, item: str, treatment: str, detail: str) -> None:
        rows.append({"Area": area, "Item": item, "Treatment": treatment, "Detail": detail})

    if tuition_claim_override > 0:
        add(
            "Schedule 11",
            "Current-year tuition claim",
            "Manual override used",
            f"You entered a direct current-year tuition claim override of {format_currency(tuition_claim_override)}.",
        )
    elif result.get("schedule11_current_year_tuition_available", 0.0) > 0:
        add(
            "Schedule 11",
            "Current-year tuition claim",
            "Auto / slip-based flow",
            f"The app used the T2202-driven Schedule 11 flow and claimed {format_currency(result.get('schedule11_current_year_claim_used', 0.0))}.",
        )

    if t2209_net_income_override > 0:
        add(
            "T2209",
            "Net income used for foreign tax credit limit",
            "Manual override used",
            f"The T2209 limit used a manual net-income override of {format_currency(t2209_net_income_override)} instead of the return net income.",
        )
    elif result.get("federal_foreign_tax_credit", 0.0) > 0:
        add(
            "T2209",
            "Net income used for foreign tax credit limit",
            "Return value used",
            f"The app used return net income of {format_currency(result.get('t2209_net_income', 0.0))} in the T2209 limit flow.",
        )

    if t2209_basic_federal_tax_override > 0:
        add(
            "T2209",
            "Basic federal tax used",
            "Manual override used",
            f"The T2209 federal limit used a manual basic-federal-tax override of {format_currency(t2209_basic_federal_tax_override)}.",
        )
    elif result.get("federal_foreign_tax_credit", 0.0) > 0:
        add(
            "T2209",
            "Basic federal tax used",
            "Calculated value used",
            f"The app used calculated federal tax of {format_currency(result.get('t2209_basic_federal_tax_used', 0.0))} in the foreign tax credit ceiling.",
        )

    if t2036_provincial_tax_otherwise_payable_override > 0:
        add(
            "T2036",
            f"{province_name} tax otherwise payable",
            "Manual override used",
            f"The provincial foreign tax credit used a manual override of {format_currency(t2036_provincial_tax_otherwise_payable_override)}.",
        )
    elif result.get("provincial_foreign_tax_credit", 0.0) > 0:
        add(
            "T2036",
            f"{province_name} tax otherwise payable",
            "Calculated value used",
            f"The app used {format_currency(result.get('provincial_tax_otherwise_payable', 0.0))} as provincial tax otherwise payable.",
        )

    cwb_manual = result.get("canada_workers_benefit_manual", 0.0)
    cwb_auto = result.get("canada_workers_benefit_auto", 0.0)
    if cwb_manual > 0:
        add(
            "Refundable credits",
            "Canada Workers Benefit",
            "Manual override used",
            f"The final CWB used the manual amount of {format_currency(cwb_manual)}. Auto estimate was {format_currency(cwb_auto)}.",
        )
    elif cwb_auto > 0:
        add(
            "Refundable credits",
            "Canada Workers Benefit",
            "Auto estimate used",
            f"The app auto-estimated CWB at {format_currency(result.get('canada_workers_benefit', 0.0))}.",
        )

    training_manual = result.get("canada_training_credit_manual", 0.0)
    training_auto = result.get("canada_training_credit_auto", 0.0)
    if training_manual > 0:
        add(
            "Refundable credits",
            "Canada Training Credit",
            "Manual override used",
            f"The final training credit used the manual amount of {format_currency(training_manual)}. Auto estimate was {format_currency(training_auto)}.",
        )
    elif training_auto > 0:
        add(
            "Refundable credits",
            "Canada Training Credit",
            "Auto estimate used",
            f"The app auto-estimated the Canada Training Credit at {format_currency(result.get('canada_training_credit', 0.0))}.",
        )

    medical_manual = result.get("medical_expense_supplement_manual", 0.0)
    medical_auto = result.get("medical_expense_supplement_auto", 0.0)
    if medical_manual > 0:
        add(
            "Refundable credits",
            "Medical Expense Supplement",
            "Manual override used",
            f"The final medical supplement used the manual amount of {format_currency(medical_manual)}. Auto estimate was {format_currency(medical_auto)}.",
        )
    elif medical_auto > 0:
        add(
            "Refundable credits",
            "Medical Expense Supplement",
            "Auto estimate used",
            f"The app auto-estimated the medical expense supplement at {format_currency(result.get('medical_expense_supplement', 0.0))}.",
        )

    if result.get("schedule11_carryforward_claim_requested", 0.0) > result.get("schedule11_carryforward_claim_used", 0.0):
        add(
            "Schedule 11",
            "Tuition carryforward claim",
            "Capped by available amount",
            f"Requested {format_currency(result.get('schedule11_carryforward_claim_requested', 0.0))}, but only {format_currency(result.get('schedule11_carryforward_claim_used', 0.0))} was used.",
        )

    if result.get("net_capital_loss_carryforward_requested", 0.0) > result.get("net_capital_loss_carryforward", 0.0):
        add(
            "Schedule 3",
            "Net capital loss carryforward",
            "Capped by current-year gain",
            f"Requested {format_currency(result.get('net_capital_loss_carryforward_requested', 0.0))}, but only {format_currency(result.get('net_capital_loss_carryforward', 0.0))} could be used.",
        )

    if result.get("schedule9_carryforward_claim_requested", 0.0) > result.get("schedule9_carryforward_claim_used", 0.0):
        add(
            "Schedule 9",
            "Donation carryforward",
            "Capped by available amount / regular limit",
            f"Requested {format_currency(result.get('schedule9_carryforward_claim_requested', 0.0))}, but only {format_currency(result.get('schedule9_carryforward_claim_used', 0.0))} was used.",
        )

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


def build_filing_readiness_df(
    result: dict,
    diagnostics: list[tuple[str, str, str]],
    postcalc_diagnostics: list[tuple[str, str, str]],
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


def build_client_summary_df(result: dict, province_name: str) -> pd.DataFrame:
    return build_currency_df(
        [
            {"Section": "Income", "Item": "Total income included", "Amount": result.get("total_income", 0.0)},
            {"Section": "Income", "Item": "Net income after deductions", "Amount": result.get("net_income", 0.0)},
            {"Section": "Income", "Item": "Taxable income", "Amount": result.get("taxable_income", 0.0)},
            {"Section": "Income Tax", "Item": "Federal tax", "Amount": result.get("federal_tax", 0.0)},
            {"Section": "Income Tax", "Item": f"{province_name} tax", "Amount": result.get("provincial_tax", 0.0)},
            {"Section": "Income Tax", "Item": "Total income tax payable", "Amount": result.get("total_payable", 0.0)},
            {"Section": "Payroll Contributions", "Item": "CPP and EI contributions", "Amount": result.get("total_cpp", 0.0) + result.get("ei", 0.0)},
            {"Section": "Credits and Payments", "Item": "Total deductions used", "Amount": result.get("total_deductions", 0.0)},
            {"Section": "Credits and Payments", "Item": "Non-refundable credits used", "Amount": result.get("federal_non_refundable_credits", 0.0) + result.get("provincial_non_refundable_credits", 0.0)},
            {"Section": "Credits and Payments", "Item": "Refundable credits used", "Amount": result.get("refundable_credits", 0.0)},
            {"Section": "Credits and Payments", "Item": "Income tax withheld, instalments, and other payments", "Amount": result.get("income_tax_withheld", 0.0) + result.get("installments_paid", 0.0) + result.get("other_payments", 0.0)},
            {"Section": "Outcome", "Item": "Estimated refund", "Amount": result.get("line_48400_refund", 0.0)},
            {"Section": "Outcome", "Item": "Estimated balance owing", "Amount": result.get("line_48500_balance_owing", 0.0)},
        ],
        ["Amount"],
    )


def build_client_key_drivers_df(result: dict, province_name: str) -> pd.DataFrame:
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


def build_printable_client_summary_html(
    result: dict,
    province_name: str,
    readiness_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    include_cta: bool = True,
) -> str:
    notes = build_client_summary_notes(result, readiness_df, province_name)
    readiness_counts = {
        "Ready": int((readiness_df["Status"] == "Ready").sum()) if not readiness_df.empty else 0,
        "Review": int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0,
        "Missing": int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0,
    }
    driver_lines = "".join(
        f"<li><strong>{row['Item']}</strong>: {row['Amount']}</li>"
        for _, row in drivers_df.iterrows()
    ) or "<li>No major deductions, credits, or payment drivers are standing out yet.</li>"
    note_lines = "".join(f"<li>{note}</li>" for note in notes)
    outcome_label = "Estimated Refund" if result.get("line_48400_refund", 0.0) > 0 else "Estimated Balance Owing" if result.get("line_48500_balance_owing", 0.0) > 0 else "Current Outcome"
    outcome_value = result.get("line_48400_refund", 0.0) if result.get("line_48400_refund", 0.0) > 0 else result.get("line_48500_balance_owing", 0.0) if result.get("line_48500_balance_owing", 0.0) > 0 else abs(result.get("refund_or_balance", 0.0))
    outcome_bg = "#ecfdf3" if result.get("line_48400_refund", 0.0) > 0 else "#fff7ed" if result.get("line_48500_balance_owing", 0.0) > 0 else "#f9fafb"
    outcome_border = "#10b981" if result.get("line_48400_refund", 0.0) > 0 else "#f59e0b" if result.get("line_48500_balance_owing", 0.0) > 0 else "#d1d5db"
    cta_text = build_client_summary_cta(result)
    cta_block = ""
    if include_cta:
        cta_block = f"""
        <div style="margin-top:20px; padding:14px 0 0 0; color:inherit;">
            <div style="font-size:0.82rem; text-transform:uppercase; letter-spacing:0.04em; opacity:0.7;">Next Step</div>
            <div style="margin-top:6px; line-height:1.5; color:inherit; opacity:0.9;">{cta_text}</div>
        </div>
        """
    return f"""
    <div style="font-family:Georgia, 'Times New Roman', serif; background:transparent; color:inherit; padding:4px 0 0 0; border:none; border-radius:0;">
        <h2 style="margin:0 0 6px 0;">Tax Estimate Summary</h2>
        <div style="margin-bottom:20px; opacity:0.8;">Province: {province_name}</div>
        <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:20px;">
            <div style="border:1px solid rgba(127,127,127,0.35); border-radius:12px; padding:12px; background:transparent;"><div style="font-size:0.8rem; opacity:0.72;">Total Income</div><div style="font-size:1.4rem; font-weight:700; color:inherit;">{format_currency(result.get('total_income', 0.0))}</div></div>
            <div style="border:1px solid rgba(127,127,127,0.35); border-radius:12px; padding:12px; background:transparent;"><div style="font-size:0.8rem; opacity:0.72;">Taxable Income</div><div style="font-size:1.4rem; font-weight:700; color:inherit;">{format_currency(result.get('taxable_income', 0.0))}</div></div>
            <div style="border:1px solid rgba(127,127,127,0.35); border-radius:12px; padding:12px; background:transparent;"><div style="font-size:0.8rem; opacity:0.72;">Total Income Tax Payable</div><div style="font-size:1.4rem; font-weight:700; color:inherit;">{format_currency(result.get('total_payable', 0.0))}</div></div>
            <div style="border:1px solid rgba(127,127,127,0.35); border-radius:12px; padding:12px; background:transparent;"><div style="font-size:0.8rem; opacity:0.72;">Income Tax Withheld</div><div style="font-size:1.4rem; font-weight:700; color:inherit;">{format_currency(result.get('income_tax_withheld', 0.0))}</div></div>
        </div>
        <div style="margin:0 0 28px 0; padding:18px 20px; border-radius:14px; border:1px solid rgba(127,127,127,0.4); background:transparent;">
            <div style="font-size:0.85rem; opacity:0.72; text-transform:uppercase; letter-spacing:0.04em;">{outcome_label}</div>
            <div style="font-size:2rem; font-weight:700; margin-top:4px; color:inherit;">{format_currency(outcome_value)}</div>
        </div>
        <h3 style="margin:28px 0 10px 0; color:inherit;">Summary</h3>
        <table style="width:100%; border-collapse:collapse; margin-bottom:18px; color:inherit;">
            <tr><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25);">Net income after deductions</td><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25); text-align:right;">{format_currency(result.get('net_income', 0.0))}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25);">Federal tax</td><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25); text-align:right;">{format_currency(result.get('federal_tax', 0.0))}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25);">{province_name} tax</td><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25); text-align:right;">{format_currency(result.get('provincial_tax', 0.0))}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25);">Total deductions used</td><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25); text-align:right;">{format_currency(result.get('total_deductions', 0.0))}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25);">Refundable credits used</td><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25); text-align:right;">{format_currency(result.get('refundable_credits', 0.0))}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25);">Income tax withheld, instalments, and other payments</td><td style="padding:8px; border-bottom:1px solid rgba(127,127,127,0.25); text-align:right;">{format_currency(result.get('income_tax_withheld', 0.0) + result.get('installments_paid', 0.0) + result.get('other_payments', 0.0))}</td></tr>
        </table>
        <h3 style="margin:18px 0 8px 0; color:inherit;">Main Factors Affecting The Result</h3>
        <ul style="margin:0 0 18px 18px; color:inherit;">{driver_lines}</ul>
        <h3 style="margin:18px 0 8px 0; color:inherit;">Filing-Readiness Snapshot</h3>
        <p style="margin:0 0 8px 0; color:inherit;">Ready: <strong>{readiness_counts['Ready']}</strong> | Review: <strong>{readiness_counts['Review']}</strong> | Missing: <strong>{readiness_counts['Missing']}</strong></p>
        <h3 style="margin:18px 0 8px 0; color:inherit;">Notes</h3>
        <ul style="margin:0 0 0 18px; color:inherit;">{note_lines}</ul>
        {cta_block}
    </div>
    """

def build_printable_client_summary_pdf(
    result: dict,
    province_name: str,
    readiness_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> bytes:
    notes = build_client_summary_notes(result, readiness_df, province_name)
    cta_text = build_client_summary_cta(result)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    left = 54
    right = width - 54
    top = height - 54
    line_height = 16
    section_gap = 12
    y = top
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    logo_path = Path(__file__).resolve().parent / "contexta_logo.png"
    accent_stroke = (0.85, 0.88, 0.92)
    accent_fill = (0.96, 0.98, 1.0)
    accent_text = (0.3, 0.35, 0.42)

    def new_page() -> None:
        nonlocal y
        pdf.showPage()
        y = top
        draw_footer()

    def write_line(text: str, font: str = "Helvetica", size: int = 10, indent: int = 0) -> None:
        nonlocal y
        if y < 70:
            new_page()
        pdf.setFont(font, size)
        pdf.drawString(left + indent, y, str(text))
        y -= line_height

    def draw_footer() -> None:
        pdf.setStrokeColorRGB(*accent_stroke)
        pdf.line(left, 34, right, 34)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(0.4, 0.45, 0.52)
        pdf.drawString(left, 22, "Contexta Advanced Personal Tax Estimator")
        pdf.drawCentredString(width / 2, 22, f"Page {pdf.getPageNumber()}")
        pdf.drawRightString(right, 22, f"Generated: {generated_at}")
        pdf.setFillColorRGB(0, 0, 0)

    def write_section_title(text: str) -> None:
        nonlocal y
        if y < 86:
            new_page()
        y -= 2
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(left, y, text)
        pdf.setStrokeColorRGB(*accent_stroke)
        pdf.line(left, y - 5, right, y - 5)
        y -= line_height + 3

    pdf.setTitle("Tax Estimate Summary")
    if logo_path.exists():
        try:
            logo_reader = ImageReader(str(logo_path))
            logo_width, logo_height = logo_reader.getSize()
            max_logo_width = 145
            max_logo_height = 44
            scale = min(max_logo_width / logo_width, max_logo_height / logo_height)
            draw_width = logo_width * scale
            draw_height = logo_height * scale
            baseline_y = y - 8
            pdf.drawImage(
                logo_reader,
                left,
                baseline_y,
                width=draw_width,
                height=draw_height,
                mask="auto",
            )
        except Exception:
            pass
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawRightString(right, y, "Tax Estimate Summary")
    divider_y = min(y - 8, baseline_y - 8 if 'baseline_y' in locals() else y - 8)
    pdf.setStrokeColorRGB(*accent_stroke)
    pdf.line(left, divider_y, right, divider_y)
    y = divider_y - 12
    write_line(f"Province: {province_name}", "Helvetica", 10)
    write_line(f"Generated on: {generated_at}", "Helvetica", 10)
    y -= section_gap

    write_line(f"Total Income: {format_currency(result.get('total_income', 0.0))}", "Helvetica-Bold", 11)
    write_line(f"Taxable Income: {format_currency(result.get('taxable_income', 0.0))}")
    write_line(f"Total Income Tax Payable: {format_currency(result.get('total_payable', 0.0))}")
    write_line(f"Income Tax Withheld: {format_currency(result.get('income_tax_withheld', 0.0))}")
    y -= section_gap

    outcome_label = "Estimated Refund" if result.get("line_48400_refund", 0.0) > 0 else "Estimated Balance Owing" if result.get("line_48500_balance_owing", 0.0) > 0 else "Current Outcome"
    outcome_value = result.get("line_48400_refund", 0.0) if result.get("line_48400_refund", 0.0) > 0 else result.get("line_48500_balance_owing", 0.0) if result.get("line_48500_balance_owing", 0.0) > 0 else abs(result.get("refund_or_balance", 0.0))
    if y < 120:
        new_page()
    box_top = y
    box_height = 44
    pdf.setStrokeColorRGB(0.55, 0.64, 0.75)
    pdf.setFillColorRGB(*accent_fill)
    if result.get("line_48400_refund", 0.0) > 0:
        pdf.setStrokeColorRGB(0.06, 0.72, 0.51)
        pdf.setFillColorRGB(0.93, 0.99, 0.95)
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        pdf.setStrokeColorRGB(0.96, 0.62, 0.04)
        pdf.setFillColorRGB(1.0, 0.97, 0.92)
    pdf.roundRect(left, box_top - box_height, right - left, box_height, 10, stroke=1, fill=1)
    pdf.setFillColorRGB(*accent_text)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(left + 12, box_top - 15, outcome_label)
    pdf.setFillColorRGB(0.07, 0.1, 0.15)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left + 12, box_top - 34, format_currency(outcome_value))
    pdf.setFillColorRGB(0, 0, 0)
    y -= box_height + 22

    write_section_title("Summary")
    write_line(f"Net income after deductions: {format_currency(result.get('net_income', 0.0))}")
    write_line(f"Federal tax: {format_currency(result.get('federal_tax', 0.0))}")
    write_line(f"{province_name} tax: {format_currency(result.get('provincial_tax', 0.0))}")
    write_line(f"Total deductions used: {format_currency(result.get('total_deductions', 0.0))}")
    write_line(f"Refundable credits used: {format_currency(result.get('refundable_credits', 0.0))}")
    write_line(
        f"Income tax withheld, instalments, and other payments: {format_currency(result.get('income_tax_withheld', 0.0) + result.get('installments_paid', 0.0) + result.get('other_payments', 0.0))}"
    )
    y -= section_gap

    write_section_title("Main Factors Affecting The Result")
    if drivers_df.empty:
        write_line("- No major deductions, credits, or payment drivers are standing out yet.")
    else:
        for _, row in drivers_df.iterrows():
            write_line(f"- {row['Item']}: {row['Amount']}")
    y -= section_gap

    ready_count = int((readiness_df["Status"] == "Ready").sum()) if not readiness_df.empty else 0
    review_count = int((readiness_df["Status"] == "Review").sum()) if not readiness_df.empty else 0
    missing_count = int((readiness_df["Status"] == "Missing").sum()) if not readiness_df.empty else 0
    write_section_title("Filing-Readiness Snapshot")
    write_line(f"Ready: {ready_count} | Review: {review_count} | Missing: {missing_count}")
    y -= section_gap

    write_section_title("Notes")
    for note in notes:
        write_line(f"- {note}")
    y -= section_gap
    write_section_title("Next Step")
    write_line(cta_text)

    draw_footer()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


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

def render_diagnostics_panel(checks: list[tuple[str, str, str]]) -> None:
    severity_styles = {
        "High": {"bg": "#7f1d1d", "fg": "#fecaca"},
        "Warning": {"bg": "#78350f", "fg": "#fde68a"},
        "Info": {"bg": "#1e3a8a", "fg": "#bfdbfe"},
    }
    severity_counts = {
        "High": sum(1 for severity, _, _ in checks if severity == "High"),
        "Warning": sum(1 for severity, _, _ in checks if severity == "Warning"),
        "Info": sum(1 for severity, _, _ in checks if severity == "Info"),
    }
    render_metric_row(
        [
            ("High-Risk", float(severity_counts["High"])),
            ("Warnings", float(severity_counts["Warning"])),
            ("Info", float(severity_counts["Info"])),
        ],
        3,
    )
    for severity, category, message in checks:
        style = severity_styles.get(severity, {"bg": "#374151", "fg": "#f3f4f6"})
        st.markdown(
            f"""
            <div style="border:1px solid #2a2f3a;border-radius:12px;padding:12px 14px;margin:8px 0;background:#111827;">
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px;">
                    <span style="background:{style['bg']};color:{style['fg']};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{severity}</span>
                    <span style="color:#d1d5db;font-size:0.85rem;font-weight:600;">{category}</span>
                </div>
                <div style="color:#f9fafb;line-height:1.45;">{message}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


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


def render_household_review_panel(result: dict) -> None:
    status_styles = {
        "Allowed": {"bg": "#14532d", "fg": "#bbf7d0"},
        "Blocked": {"bg": "#7f1d1d", "fg": "#fecaca"},
    }
    household_rows = [
        {
            "claim": "Spouse amount",
            "status": "Allowed" if result.get("household_spouse_allowed", 0.0) else "Blocked",
            "requested": result.get("manual_spouse_claim", 0.0),
            "used": result.get("effective_spouse_claim", 0.0),
            "reason": result.get("household_spouse_reason", ""),
        },
        {
            "claim": "Eligible dependant amount",
            "status": "Allowed" if result.get("household_eligible_dependant_allowed", 0.0) else "Blocked",
            "requested": result.get("manual_eligible_dependant_claim", 0.0),
            "used": result.get("effective_eligible_dependant_claim", 0.0),
            "reason": result.get("household_eligible_dependant_reason", ""),
        },
        {
            "claim": "Caregiver amount",
            "status": "Allowed" if result.get("household_caregiver_allowed", 0.0) else "Blocked",
            "requested": result.get("requested_caregiver_claim", 0.0),
            "available": result.get("available_caregiver_claim", 0.0),
            "used": result.get("provincial_caregiver_claim_amount", 0.0),
            "unused": result.get("unused_caregiver_claim", 0.0),
            "reason": result.get("household_caregiver_reason", ""),
        },
        {
            "claim": "Disability transfer",
            "status": "Allowed" if result.get("household_disability_transfer_allowed", 0.0) else "Blocked",
            "requested": result.get("requested_disability_transfer", 0.0),
            "available": result.get("available_disability_transfer", 0.0),
            "used": result.get("household_disability_transfer_used", 0.0),
            "unused": result.get("unused_disability_transfer", 0.0),
            "reason": result.get("household_disability_transfer_reason", ""),
        },
        {
            "claim": "Medical for dependants",
            "status": "Allowed" if result.get("household_medical_dependants_allowed", 0.0) else "Blocked",
            "requested": result.get("requested_medical_dependants", 0.0),
            "available": result.get("available_medical_dependants", 0.0),
            "used": result.get("household_medical_dependants_used", 0.0),
            "unused": result.get("unused_medical_dependants", 0.0),
            "reason": result.get("household_medical_dependants_reason", ""),
        },
    ]
    render_metric_row(
        [
            ("Allowed", float(sum(1 for row in household_rows if row["status"] == "Allowed"))),
            ("Blocked", float(sum(1 for row in household_rows if row["status"] == "Blocked"))),
        ],
        2,
    )
    for row in household_rows:
        style = status_styles[row["status"]]
        st.markdown(
            f"""
            <div style="border:1px solid #2a2f3a;border-radius:12px;padding:12px 14px;margin:8px 0;background:#111827;">
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px;">
                    <span style="background:{style['bg']};color:{style['fg']};padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;">{row['status']}</span>
                    <span style="color:#f9fafb;font-weight:600;">{row['claim']}</span>
                </div>
                <div style="color:#d1d5db;line-height:1.5;">
                    Requested: {format_currency(row['requested'])}<br>
                    Available: {format_currency(row.get('available', row['requested']))}<br>
                    Used: {format_currency(row['used'])}<br>
                    Unused: {format_currency(row.get('unused', 0.0))}<br>
                    {row['reason']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    allocation_trace = build_currency_df(
        [
            {"Step": "1", "Flow": "Spouse amount", "Requested": result.get("manual_spouse_claim", 0.0), "Used": result.get("effective_spouse_claim", 0.0)},
            {"Step": "2", "Flow": "Eligible dependant", "Requested": result.get("manual_eligible_dependant_claim", 0.0), "Used": result.get("effective_eligible_dependant_claim", 0.0)},
            {"Step": "3", "Flow": "Caregiver pool", "Requested": result.get("requested_caregiver_claim", 0.0), "Used": result.get("provincial_caregiver_claim_amount", 0.0)},
            {"Step": "4", "Flow": "Disability transfer", "Requested": result.get("requested_disability_transfer", 0.0), "Used": result.get("household_disability_transfer_used", 0.0)},
            {"Step": "5", "Flow": "Dependant medical", "Requested": result.get("requested_medical_dependants", 0.0), "Used": result.get("household_medical_dependants_used", 0.0)},
        ],
        ["Requested", "Used"],
    )
    st.markdown("#### Household Allocation Trace")
    st.dataframe(allocation_trace, use_container_width=True, hide_index=True)
    if result.get("additional_dependant_count", 0.0):
        st.caption(
            f"Additional dependants in pool: {int(result.get('additional_dependant_count', 0.0))}. "
            f"Additional caregiver pool: {format_currency(result.get('additional_dependant_caregiver_claim_total', 0.0))}. "
            f"Additional disability transfer pool: {format_currency(result.get('additional_dependant_disability_transfer_available_total', 0.0))}. "
            f"Additional medical pool: {format_currency(result.get('additional_dependant_medical_claim_total', 0.0))}."
        )


def collect_diagnostics(context: dict[str, float | int | bool]) -> list[tuple[str, str, str]]:
    checks: list[tuple[str, str, str]] = []

    def add(severity: str, category: str, message: str) -> None:
        checks.append((severity, category, message))

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
    if context["spouse_claim_enabled"] and not context["has_spouse_end_of_year"]:
        add("Warning", "Household", "Spouse amount is selected, but 'Had Spouse at Year End' is not checked.")
    if context["spouse_claim_enabled"] and context["support_payments_to_spouse"]:
        add("High", "Household", "Spouse amount is selected while support payments to the spouse/common-law partner are indicated.")
    if context["spouse_claim_enabled"] and context["separated_in_year"]:
        add("Warning", "Household", "Spouse amount is selected while 'Separated in Year' is checked. Review whether the spouse amount should still be claimed.")
    if context["eligible_dependant_claim_enabled"] and not context["dependant_lived_with_you"]:
        add("Warning", "Household", "Eligible dependant is selected, but 'Dependant Lived With You' is not checked.")
    if context["eligible_dependant_claim_enabled"] and context["dependant_relationship"] == "Other":
        add("High", "Household", "Eligible dependant is selected, but the dependant relationship is marked as 'Other'.")
    if context["eligible_dependant_claim_enabled"] and context["dependant_category"] == "Other":
        add("High", "Household", "Eligible dependant is selected, but the dependant category is marked as 'Other'.")
    if context["paid_child_support_for_dependant"] and not context["shared_custody_claim_agreement"] and context["eligible_dependant_claim_enabled"]:
        add("High", "Household", "Eligible dependant is selected while child support is paid and no shared-custody agreement is indicated.")
    if context["another_household_member_claims_dependant"] and context["eligible_dependant_claim_enabled"]:
        add("High", "Household", "Eligible dependant is selected, but another household member is also marked as claiming the dependant.")
    if context["another_household_member_claims_caregiver"] and context["caregiver_claim_amount"] > 0:
        add("High", "Household", "A caregiver amount is entered, but another household member is already marked as claiming the caregiver amount.")
    if context["caregiver_claim_amount"] > 0 and context["caregiver_claim_target"] == "Auto" and context["spouse_infirm"] and context["eligible_dependant_infirm"]:
        add("Warning", "Household", "Caregiver amount is entered while both spouse and dependant are infirm. Pick a caregiver target to avoid ambiguity.")
    if context["caregiver_claim_amount"] > 0 and context["eligible_dependant_infirm"] and context["dependant_category"] not in {"Adult child", "Parent/Grandparent", "Other adult relative"}:
        add("Warning", "Household", "A caregiver amount is entered for an infirm dependant, but the dependant category does not indicate an adult dependant.")
    if context["caregiver_claim_amount"] > 0 and not (context["spouse_infirm"] or context["eligible_dependant_infirm"] or context["dependant_lived_with_you"]):
        add("Info", "Household", "A caregiver amount is entered, but no infirm spouse/dependant or dependant living arrangement is indicated.")
    if context["another_household_member_claims_disability_transfer"] and context["ontario_disability_transfer"] > 0:
        add("High", "Household", "A disability transfer is entered, but another household member is already marked as claiming the disability transfer.")
    if context["ontario_disability_transfer"] > 0 and context["disability_transfer_source"] == "Auto" and context["spouse_infirm"] and context["eligible_dependant_infirm"]:
        add("Warning", "Household", "Disability transfer is entered while both spouse and dependant could qualify. Pick a transfer source to avoid ambiguity.")
    if context["ontario_disability_transfer"] > 0 and context["spouse_infirm"] and not context["spouse_disability_transfer_available"]:
        add("Warning", "Household", "A disability transfer is entered for the spouse, but no unused spouse disability transfer is indicated.")
    if context["ontario_disability_transfer"] > 0 and context["eligible_dependant_infirm"] and not context["dependant_disability_transfer_available"]:
        add("Warning", "Household", "A disability transfer is entered for a dependant, but no unused dependant disability transfer is indicated.")
    if context["ontario_disability_transfer"] > context["spouse_disability_transfer_available_amount"] and context["disability_transfer_source"] == "Spouse" and context["spouse_disability_transfer_available_amount"] > 0:
        add("Info", "Household", "Requested disability transfer exceeds the spouse amount available. The app caps it to the available spouse transfer.")
    if context["ontario_disability_transfer"] > context["dependant_disability_transfer_available_amount"] and context["disability_transfer_source"] == "Dependant" and context["dependant_disability_transfer_available_amount"] > 0:
        add("Info", "Household", "Requested disability transfer exceeds the dependant amount available. The app caps it to the available dependant transfer.")
    if context["ontario_disability_transfer"] > 0 and not (context["spouse_claim_enabled"] or context["eligible_dependant_claim_enabled"] or context["dependant_lived_with_you"]):
        add("Info", "Household", "A disability transfer is entered, but no qualifying spouse/dependant relationship is indicated.")
    if context["medical_dependant_claim_shared"] and context["ontario_medical_dependants"] > 0:
        add("Warning", "Household", "Medical for other dependants is entered while another person is marked as sharing or claiming that dependant medical amount.")
    if context["ontario_medical_dependants"] > 0 and context["dependant_category"] == "Minor child":
        add("Info", "Household", "Medical for other dependants is entered while the dependant category is marked as a minor child. Review whether this amount belongs in the dependant-medical section.")

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
    if context["cwb_disability_supplement_eligible"] and context["canada_workers_benefit_auto"] == 0:
        add("Info", "Refundable credits", "CWB disability supplement eligibility is checked, but the app did not produce an automatic CWB amount. Review working income and adjusted net income inputs.")
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


def collect_postcalc_diagnostics(result: dict[str, float]) -> list[tuple[str, str, str]]:
    checks: list[tuple[str, str, str]] = []

    def add(severity: str, category: str, message: str) -> None:
        checks.append((severity, category, message))

    cwb_manual = result.get("canada_workers_benefit_manual", 0.0)
    cwb_auto = result.get("canada_workers_benefit_auto", 0.0)
    cwb_used = result.get("canada_workers_benefit", 0.0)
    if cwb_manual > 0 and abs(cwb_manual - cwb_auto) > 100.0:
        add("Info", "Refundable credits", "Manual Canada Workers Benefit override differs materially from the app's auto estimate. Review the CWB worksheet if you entered the amount manually.")
    if cwb_used == 0 and cwb_auto > 0:
        add("Info", "Refundable credits", "The app calculated a positive Canada Workers Benefit estimate, but it was not used. Review whether a manual override or another input suppressed it.")
    if result.get("cwb_disability_supplement_auto", 0.0) > 0:
        add("Info", "Refundable credits", "The final Canada Workers Benefit includes a disability supplement estimate.")
    if result.get("cwb_disability_supplement_eligible", 0.0) > 0 and result.get("canada_workers_benefit_manual", 0.0) > 0:
        add("Info", "Refundable credits", "A manual Canada Workers Benefit override is being used while CWB disability supplement eligibility is checked. Review whether the manual total already includes the supplement.")

    training_manual = result.get("canada_training_credit_manual", 0.0)
    training_auto = result.get("canada_training_credit_auto", 0.0)
    training_limit = result.get("canada_training_credit_limit_available", 0.0)
    if training_manual > 0 and training_limit > 0 and training_manual > training_limit:
        add("Warning", "Refundable credits", "Manual Canada Training Credit exceeds the training credit limit available entered. The app used the manual override, so review the Schedule 11 / training-credit worksheet.")
    if training_auto == 0 and training_limit > 0 and result.get("schedule11_current_year_claim_used", 0.0) == 0:
        add("Info", "Refundable credits", "A training credit limit is available, but no current-year tuition/training claim was used. The automatic Canada Training Credit therefore stayed at zero.")

    medical_manual = result.get("medical_expense_supplement_manual", 0.0)
    medical_auto = result.get("medical_expense_supplement_auto", 0.0)
    if medical_manual > 0 and abs(medical_manual - medical_auto) > 100.0:
        add("Info", "Refundable credits", "Manual Medical Expense Supplement override differs materially from the app's auto estimate. Review the supplement worksheet if you entered it manually.")
    if medical_auto == 0 and result.get("medical_expense_supplement", 0.0) == 0 and result.get("federal_medical_claim", 0.0) > 0:
        add("Info", "Refundable credits", "A federal medical claim exists, but no Medical Expense Supplement was produced. This can be correct if income thresholds are not met.")

    cpp_refund = result.get("cpp_overpayment_refund", 0.0)
    ei_refund = result.get("ei_overpayment_refund", 0.0)
    if cpp_refund > 0:
        add("Info", "Payroll refund", "CPP withheld on slips is above the app's employee CPP estimate, so a CPP overpayment refund estimate was included.")
    if ei_refund > 0:
        add("Info", "Payroll refund", "EI withheld on slips is above the app's EI estimate, so an EI overpayment refund estimate was included.")

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
            cols = st.columns(2)
            record: dict[str, object] = {}
            for field_index, field in enumerate(fields):
                col = cols[field_index % 2]
                field_id = str(field["id"])
                field_type = str(field.get("type", "number"))
                widget_key = f"{card_key}_{index}_{field_id}"
                if field_type == "text":
                    record[field_id] = col.text_input(
                        str(field["label"]),
                        value=str(st.session_state.get(widget_key, field.get("value", ""))),
                        key=widget_key,
                        help=str(field.get("help", "")) if field.get("help") else None,
                        placeholder=str(field.get("placeholder", "")) if field.get("placeholder") else None,
                    )
                elif field_type == "select":
                    options = list(field.get("options", []))
                    default_value = st.session_state.get(widget_key, field.get("value", options[0] if options else ""))
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
                            value=float(st.session_state.get(widget_key, field.get("value", 0.0))),
                            key=widget_key,
                            help=str(field.get("help", "")) if field.get("help") else None,
                        )
                    )
            records.append(record)
    st.session_state[card_key] = records
    return pd.DataFrame(records)


def render_t_slip_wizard_card(title: str, card_key: str, fields: list[dict[str, object]], count_default: int = 1) -> list[dict[str, float]]:
    st.markdown(f"#### {title}")
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


def build_wizard_df(records: list[dict[str, float]], columns: list[str]) -> pd.DataFrame:
    return coerce_editor_df(pd.DataFrame(records or empty_rows(columns, 0)), columns)


def line_summary_df(result: dict, province_name: str) -> pd.DataFrame:
    rows = [
        {"Line": "10100", "Description": "Employment income", "Amount": result.get("line_10100", 0.0)},
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
        {"Line": "22200", "Description": "Dues", "Amount": result.get("line_union_dues", 0.0)},
        {"Line": "22900", "Description": "Other employment expenses", "Amount": result.get("line_other_employment_expenses", 0.0)},
        {"Line": "23600", "Description": "Net income", "Amount": result.get("net_income", 0.0)},
        {"Line": "25300", "Description": "Net capital loss carryforward", "Amount": result.get("net_capital_loss_carryforward", 0.0)},
        {"Line": "26000", "Description": "Taxable income", "Amount": result.get("taxable_income", 0.0)},
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
            {"Line": "T2202", "Description": "Current-year T2202 tuition available", "Amount": result.get("schedule11_current_year_tuition_available", 0.0)},
            {"Line": "CF-Avail", "Description": "Prior-year tuition carryforward available", "Amount": result.get("schedule11_carryforward_available", 0.0)},
            {"Line": "11A", "Description": "Total tuition available", "Amount": result.get("schedule11_total_available", 0.0)},
            {"Line": "11B", "Description": "Current-year tuition claim requested", "Amount": result.get("schedule11_current_year_claim_requested", 0.0)},
            {"Line": "11C", "Description": "Current-year tuition claim used", "Amount": result.get("schedule11_current_year_claim_used", 0.0)},
            {"Line": "11D", "Description": "Carryforward claim requested", "Amount": result.get("schedule11_carryforward_claim_requested", 0.0)},
            {"Line": "11E", "Description": "Carryforward claim used", "Amount": result.get("schedule11_carryforward_claim_used", 0.0)},
            {"Line": "32300", "Description": "Federal tuition amount claimed", "Amount": result.get("schedule11_total_claim_used", 0.0)},
            {"Line": "Transfer-In", "Description": "Tuition transfer from spouse/partner", "Amount": result.get("schedule11_transfer_from_spouse", 0.0)},
            {"Line": "Unused", "Description": "Unused current-year tuition", "Amount": result.get("schedule11_current_year_unused", 0.0)},
            {"Line": "Unused-CF", "Description": "Unused carryforward remaining", "Amount": result.get("schedule11_carryforward_unused", 0.0)},
            {"Line": "11F", "Description": "Unused tuition remaining after claim", "Amount": result.get("schedule11_total_unused", 0.0)},
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


st.set_page_config(page_title=META_TITLE, page_icon="🧮", layout="wide")
inject_meta_tags()

st.title("Advanced Canadian Personal Tax Estimator")
st.caption(
    "Built for broader personal-return scenarios. It now supports employment, investment and rental "
    "income, plus common deductions, credits, and refund or balance owing estimates."
)
st.info(
    "Current scope: strong federal coverage across Canada, with Ontario and British Columbia now receiving "
    "the most detailed provincial handling. Other provinces use their core bracket and personal credit rules "
    "plus any additional provincial credit amounts you enter."
)
st.caption(
    "Auto-calculated advanced credits added in this round: federal dividend tax credit, federal medical "
    "threshold, federal age amount logic, and Ontario age, pension, medical, and tax-reduction handling for 2025."
)
st.caption(
    "This round also adds spouse and eligible dependant interaction logic, a worksheet-style foreign tax credit model, "
    "and province-aware dividend tax credit handling."
)
st.caption(
    "This round upgrades provincial handling with auto-calculated Ontario and B.C. dividend credits, B.C. tax "
    "reduction logic, improved foreign tax credit ceilings, and tighter eligible dependant restriction inputs."
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

st.subheader("1) Return Setup")
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
province_name = PROVINCES[province]

with st.container(border=True):
    st.markdown("#### Quick Start")
    st.markdown(
        """
        - `Only have T-slips?` Start with `1A) Slips and Source Records`. For many users, that may be enough.
        - `Have income not already shown on slips?` Review `2) Income and Investment`.
        - `Have RRSP, FHSA, moving expenses, or other deductions?` Review `3) Deductions`.
        - `Have donations, medical expenses, tuition carryforwards, dependants, or foreign tax situations?` Review `4) Credits, Carryforwards and Special Forms`.
        - `Made instalments or other tax payments outside your slips?` Review `5) Payments and Withholdings`.
        """
    )

with st.expander("1A) Slips and Source Records", expanded=True):
    st.caption(
        "Use the wizard cards below to copy amounts directly from your CRA slips. Quick-fill grids and duplicate slip tables stay hidden to keep the app simpler."
    )
    st.info(
        "For most T-slip-only users, filling 1A may be enough. If you only have slips like T4, T3, T4PS, or T2202, start here first and only complete later sections if you also have deductions, credits, carryforwards, or extra payments to add."
    )
    wizard_records = render_slip_wizard_tabs(SLIP_WIZARD_CONFIGS)
    st.caption("T4 Box 20 reduces current-year taxable income. T4 Box 52 is reference only for the current-year estimate and mainly affects next-year RRSP room.")
    st.caption("T4PS Box 41 is kept as reference only and does not directly change this estimate.")
    t4_wizard_records = wizard_records["t4_wizard"]
    t4a_wizard_records = wizard_records["t4a_wizard"]
    t5_wizard_records = wizard_records["t5_wizard"]
    t3_wizard_records = wizard_records["t3_wizard"]
    t4ps_wizard_records = wizard_records["t4ps_wizard"]
    t2202_wizard_records = wizard_records["t2202_wizard"]

    st.markdown("#### Property and Capital Schedules")
    property_tabs = st.tabs(["Rental Properties", "Capital Gains Schedule"])
    with property_tabs[0]:
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
    with property_tabs[1]:
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

with st.expander("2) Income and Investment (Optional if not already covered by slips)", expanded=False):
    st.caption("You can skip this section unless you have income that is not already shown on your T-slips or source-record cards above.")
    st.markdown("#### Income")
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
    eligible_dividends = number_input("Eligible Dividends (actual cash)", "eligible_dividends", 100.0)
    non_eligible_dividends = number_input("Non-Eligible Dividends (actual cash)", "non_eligible_dividends", 100.0)

    st.markdown("#### Dividend Slips")
    div_col1, div_col2, div_col3 = st.columns(3)
    t5_eligible_dividends_taxable = number_input(
        "T5 Eligible Dividends Taxable Amount",
        "t5_eligible_dividends_taxable",
        100.0,
        "Use the taxable eligible dividend amount from T5 slips if available.",
    )
    t5_non_eligible_dividends_taxable = number_input(
        "T5 Other Than Eligible Dividends Taxable Amount",
        "t5_non_eligible_dividends_taxable",
        100.0,
        "Use the taxable non-eligible dividend amount from T5 slips if available.",
    )
    t5_federal_dividend_credit = number_input(
        "T5 Federal Dividend Tax Credit",
        "t5_federal_dividend_credit",
        10.0,
        "If your T5/T3 slips already show the federal dividend tax credit, enter it here to override auto-estimation for those slips.",
    )
    t3_eligible_dividends_taxable = number_input(
        "T3 Eligible Dividends Taxable Amount",
        "t3_eligible_dividends_taxable",
        100.0,
    )
    t3_non_eligible_dividends_taxable = number_input(
        "T3 Other Than Eligible Dividends Taxable Amount",
        "t3_non_eligible_dividends_taxable",
        100.0,
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
    t5_eligible_dividends_taxable += float(t5_wizard_totals.get("box25_eligible_dividends_taxable", 0.0))
    t5_eligible_dividends_taxable += float(t4ps_wizard_totals.get("box31_eligible_dividends_taxable", 0.0))
    t5_non_eligible_dividends_taxable += float(t5_wizard_totals.get("box11_non_eligible_dividends_taxable", 0.0))
    t5_non_eligible_dividends_taxable += float(t4ps_wizard_totals.get("box25_non_eligible_dividends_taxable", 0.0))
    federal_dividend_credit_slip_total = (
        float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0))
        + float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0))
        + float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0))
        + float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0))
        + float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0))
        + float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0))
    )
    t5_federal_dividend_credit += float(t5_wizard_totals.get("box26_eligible_dividend_credit", 0.0)) + float(t5_wizard_totals.get("box12_non_eligible_dividend_credit", 0.0))
    t5_federal_dividend_credit += float(t4ps_wizard_totals.get("box26_non_eligible_dividend_credit", 0.0)) + float(t4ps_wizard_totals.get("box32_eligible_dividend_credit", 0.0))
    t3_eligible_dividends_taxable += float(t3_wizard_totals.get("box50_eligible_dividends_taxable", 0.0))
    t3_non_eligible_dividends_taxable += float(t3_wizard_totals.get("box32_non_eligible_dividends_taxable", 0.0))
    t3_federal_dividend_credit += float(t3_wizard_totals.get("box51_eligible_dividend_credit", 0.0)) + float(t3_wizard_totals.get("box39_non_eligible_dividend_credit", 0.0))

    t4_reference_box24_total = (
        float(t4_wizard_totals.get("box24_ei_insurable_earnings", 0.0))
    )
    t4_reference_box26_total = (
        float(t4_wizard_totals.get("box26_cpp_pensionable_earnings", 0.0))
    )
    t4_reference_box52_total = (
        float(t4_wizard_totals.get("box52_pension_adjustment", 0.0))
    )
    st.markdown("#### Input Totals and T4 Reference")
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
                {
                    "Group": "T4 Reference",
                    "Item": "T4 Box 24 EI Insurable Earnings",
                    "Amount": t4_reference_box24_total,
                },
                {
                    "Group": "T4 Reference",
                    "Item": "T4 Box 26 CPP Pensionable Earnings",
                    "Amount": t4_reference_box26_total,
                },
                {
                    "Group": "T4 Reference",
                    "Item": "T4 Box 52 Pension Adjustment",
                    "Amount": t4_reference_box52_total,
                },
            ],
            ["Amount"],
        ),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("3) Deductions (Optional)", expanded=False):
    st.caption("You can skip this section unless you have deductions such as RRSP, FHSA, moving expenses, child care, carrying charges, support payments, or other employment expenses.")
    ded_col1, ded_col2, ded_col3 = st.columns(3)
    rrsp_deduction = number_input("RRSP Deduction (line 20800)", "rrsp_deduction", 500.0)
    fhsa_deduction = number_input("FHSA Deduction (line 20805)", "fhsa_deduction", 500.0)
    rpp_contribution = number_input("RPP Contribution", "rpp_contribution", 500.0)
    union_dues = number_input("Union / Professional Dues (line 22200)", "union_dues", 100.0)
    child_care_expenses = number_input("Child Care Expenses (line 22100)", "child_care_expenses", 100.0)
    moving_expenses = number_input("Moving Expenses (line 21900)", "moving_expenses", 100.0)
    support_payments_deduction = number_input("Deductible Support Payments (line 22000)", "support_payments_deduction", 100.0)
    carrying_charges = number_input("Carrying Charges / Interest (line 22100/21400 style)", "carrying_charges", 100.0)
    other_employment_expenses = number_input(
        "Other Employment Expenses (line 22900)",
        "other_employment_expenses",
        100.0,
        "Use this for deductible employment expenses not already included elsewhere.",
    )
    other_deductions = number_input("Other Deductions", "other_deductions", 100.0)
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
rpp_contribution += float(t4_wizard_totals.get("box20_rpp", 0.0))
union_dues += float(t4_wizard_totals.get("box44_union_dues", 0.0))

with st.expander("4) Credits, Carryforwards and Special Forms (Optional / Situational)", expanded=False):
    st.caption("You can skip this section unless you have tuition, donations, medical expenses, dependants, foreign tax situations, carryforwards, or province-specific credits to review.")
    st.markdown("#### Household Status Wizard")
    household_tabs = st.tabs(["Marital Status", "Dependant Status", "Claim Restrictions"])
    with household_tabs[0]:
        with st.container(border=True):
            marital_col1, marital_col2 = st.columns(2)
            spouse_claim_enabled = marital_col1.checkbox(
                "Claim Spouse Amount",
                value=bool(st.session_state.get("spouse_claim_enabled", False)),
                key="spouse_claim_enabled",
            )
            has_spouse_end_of_year = marital_col1.checkbox(
                "Had Spouse at Year End",
                value=bool(st.session_state.get("has_spouse_end_of_year", False)),
                key="has_spouse_end_of_year",
            )
            separated_in_year = marital_col1.checkbox(
                "Separated in Year",
                value=bool(st.session_state.get("separated_in_year", False)),
                key="separated_in_year",
            )
            support_payments_to_spouse = marital_col1.checkbox(
                "Support Payments to Spouse",
                value=bool(st.session_state.get("support_payments_to_spouse", False)),
                key="support_payments_to_spouse",
            )
            spouse_infirm = marital_col2.checkbox(
                "Spouse Infirm",
                value=bool(st.session_state.get("spouse_infirm", False)),
                key="spouse_infirm",
            )
            spouse_disability_transfer_available = marital_col2.checkbox(
                "Spouse Has Unused Disability Transfer",
                value=bool(st.session_state.get("spouse_disability_transfer_available", False)),
                key="spouse_disability_transfer_available",
                help="Check if the spouse/common-law partner has an unused disability amount transfer available to claim.",
            )
            spouse_disability_transfer_available_amount = number_input(
                "Spouse Disability Transfer Available Amount",
                "spouse_disability_transfer_available_amount",
                100.0,
                "Optional. Enter the unused spouse disability transfer amount available before claiming it.",
            )
            spouse_net_income = number_input(
                "Spouse Net Income",
                "spouse_net_income",
                100.0,
                "Used to auto-calculate the spouse amount if the claim is enabled.",
            )
    with household_tabs[1]:
        with st.container(border=True):
            dep_col1, dep_col2 = st.columns(2)
            eligible_dependant_claim_enabled = dep_col1.checkbox(
                "Claim Eligible Dependant",
                value=bool(st.session_state.get("eligible_dependant_claim_enabled", False)),
                key="eligible_dependant_claim_enabled",
            )
            eligible_dependant_infirm = dep_col1.checkbox(
                "Eligible Dependant Infirm",
                value=bool(st.session_state.get("eligible_dependant_infirm", False)),
                key="eligible_dependant_infirm",
            )
            dependant_lived_with_you = dep_col1.checkbox(
                "Dependant Lived With You",
                value=bool(st.session_state.get("dependant_lived_with_you", False)),
                key="dependant_lived_with_you",
            )
            eligible_dependant_net_income = number_input(
                "Eligible Dependant Net Income",
                "eligible_dependant_net_income",
                100.0,
                "Used to auto-calculate the eligible dependant amount if the claim is enabled.",
            )
            dependant_relationship = dep_col2.selectbox(
                "Dependant Relationship",
                ["Child", "Parent/Grandparent", "Other relative", "Other"],
                index=["Child", "Parent/Grandparent", "Other relative", "Other"].index(str(st.session_state.get("dependant_relationship", "Child")) if str(st.session_state.get("dependant_relationship", "Child")) in ["Child", "Parent/Grandparent", "Other relative", "Other"] else "Child"),
                key="dependant_relationship",
                help="Used in household-claim restriction checks.",
            )
            dependant_category = dep_col2.selectbox(
                "Dependant Category",
                ["Minor child", "Adult child", "Parent/Grandparent", "Other adult relative", "Other"],
                index=[
                    "Minor child",
                    "Adult child",
                    "Parent/Grandparent",
                    "Other adult relative",
                    "Other",
                ].index(
                    str(st.session_state.get("dependant_category", "Minor child"))
                    if str(st.session_state.get("dependant_category", "Minor child")) in [
                        "Minor child",
                        "Adult child",
                        "Parent/Grandparent",
                        "Other adult relative",
                        "Other",
                    ]
                    else "Minor child"
                ),
                key="dependant_category",
                help="Used for finer household and transfer restriction checks.",
            )
            dependant_disability_transfer_available = dep_col2.checkbox(
                "Dependant Has Unused Disability Transfer",
                value=bool(st.session_state.get("dependant_disability_transfer_available", False)),
                key="dependant_disability_transfer_available",
                help="Check if the dependant has an unused disability amount transfer available.",
            )
            dependant_disability_transfer_available_amount = number_input(
                "Dependant Disability Transfer Available Amount",
                "dependant_disability_transfer_available_amount",
                100.0,
                "Optional. Enter the unused dependant disability transfer amount available before claiming it.",
            )
    with household_tabs[2]:
        with st.container(border=True):
            restrict_col1, restrict_col2 = st.columns(2)
            paid_child_support_for_dependant = restrict_col1.checkbox(
                "Paid Child Support for Dependant",
                value=bool(st.session_state.get("paid_child_support_for_dependant", False)),
                key="paid_child_support_for_dependant",
            )
            shared_custody_claim_agreement = restrict_col1.checkbox(
                "Shared Custody Claim Agreement",
                value=bool(st.session_state.get("shared_custody_claim_agreement", False)),
                key="shared_custody_claim_agreement",
            )
            another_household_member_claims_dependant = restrict_col1.checkbox(
                "Another Household Member Claims Dependant",
                value=bool(st.session_state.get("another_household_member_claims_dependant", False)),
                key="another_household_member_claims_dependant",
            )
            another_household_member_claims_caregiver = restrict_col2.checkbox(
                "Another Household Member Claims Caregiver Amount",
                value=bool(st.session_state.get("another_household_member_claims_caregiver", False)),
                key="another_household_member_claims_caregiver",
            )
            another_household_member_claims_disability_transfer = restrict_col2.checkbox(
                "Another Household Member Claims Disability Transfer",
                value=bool(st.session_state.get("another_household_member_claims_disability_transfer", False)),
                key="another_household_member_claims_disability_transfer",
            )
            medical_dependant_claim_shared = restrict_col2.checkbox(
                "Another Person Shares/Claims Medical for This Dependant",
                value=bool(st.session_state.get("medical_dependant_claim_shared", False)),
                key="medical_dependant_claim_shared",
            )
            caregiver_claim_target = restrict_col2.selectbox(
                "Caregiver Claim Target",
                ["Auto", "Spouse", "Dependant"],
                index=["Auto", "Spouse", "Dependant"].index(
                    str(st.session_state.get("caregiver_claim_target", "Auto"))
                    if str(st.session_state.get("caregiver_claim_target", "Auto")) in ["Auto", "Spouse", "Dependant"]
                    else "Auto"
                ),
                key="caregiver_claim_target",
                help="Use this when both spouse and dependant could qualify and you want to control which household member the caregiver claim is tied to.",
            )
            disability_transfer_source = restrict_col2.selectbox(
                "Disability Transfer Source",
                ["Auto", "Spouse", "Dependant"],
                index=["Auto", "Spouse", "Dependant"].index(
                    str(st.session_state.get("disability_transfer_source", "Auto"))
                    if str(st.session_state.get("disability_transfer_source", "Auto")) in ["Auto", "Spouse", "Dependant"]
                    else "Auto"
                ),
                key="disability_transfer_source",
                help="Choose the source of the disability transfer when both spouse and dependant could qualify.",
            )
    additional_dependants_df = render_record_card_editor(
        "Additional Dependants",
        "additional_dependants",
        [
            {"id": "dependant_label", "label": "Dependant Label", "type": "text", "placeholder": "Dependant 2"},
            {"id": "category", "label": "Category", "type": "select", "options": ["Minor child", "Adult child", "Parent/Grandparent", "Other adult relative", "Other"]},
            {"id": "infirm", "label": "Infirm", "type": "select", "options": ["No", "Yes"]},
            {"id": "lived_with_you", "label": "Lived With You", "type": "select", "options": ["No", "Yes"]},
            {"id": "caregiver_claim_amount", "label": "Caregiver Claim Amount", "step": 100.0},
            {"id": "disability_transfer_available_amount", "label": "Disability Transfer Available Amount", "step": 100.0},
            {"id": "medical_expenses_amount", "label": "Medical Expenses Amount", "step": 100.0},
            {"id": "medical_claim_shared", "label": "Medical Already Shared/Claimed by Another Person", "type": "select", "options": ["No", "Yes"]},
        ],
        "Use this for additional dependants beyond the main dependant interview. These rows currently feed caregiver, disability transfer, and dependant-medical pools.",
        count_default=0,
    )
    st.caption("Use the household wizard to describe who lived with you, who is being claimed, and whether another person is already claiming overlapping household amounts.")
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
    if additional_dependant_count:
        render_metric_row(
            [
                ("Additional Dependants", float(additional_dependant_count)),
                ("Additional Caregiver Pool", additional_dependant_caregiver_claim_total),
                ("Additional Disability Transfer Pool", additional_dependant_disability_transfer_available_total),
                ("Additional Medical Pool", additional_dependant_medical_claim_total),
            ],
            4,
        )
    spouse_amount_claim = number_input(
        "Federal Spouse / Common-Law Claim Amount",
        "spouse_amount_claim",
        100.0,
        "Enter the claim amount base, not the credit itself.",
    )
    eligible_dependant_claim = number_input(
        "Federal Eligible Dependant Claim Amount",
        "eligible_dependant_claim",
        100.0,
    )
    disability_amount_claim = number_input(
        "Federal Disability Amount Claim",
        "disability_amount_claim",
        100.0,
    )
    age_amount_claim = number_input(
        "Federal Age Amount Claim",
        "age_amount_claim",
        100.0,
        "Enter the federal age amount claim base if applicable.",
    )
    tuition_amount_claim = number_input(
        "Current-Year Tuition Claim Override",
        "tuition_amount_claim",
        100.0,
        "Leave at 0 to auto-claim the current-year T2202 tuition amount. Enter a lower or different amount only if you are following Schedule 11 manually.",
    )
    tuition_transfer_from_spouse = number_input(
        "Federal Tuition Transfer From Spouse",
        "tuition_transfer_from_spouse",
        100.0,
    )
    t2202_tuition_total = float(t2202_wizard_totals.get("box26_total_eligible_tuition", 0.0)) or float(t2202_wizard_totals.get("box23_session_tuition", 0.0))
    student_loan_interest = number_input("Student Loan Interest", "student_loan_interest", 50.0)
    medical_expenses_eligible = number_input(
        "Manual Medical Claim Amount",
        "medical_expenses_eligible",
        100.0,
        "Manual fallback. For 2025, the estimator now auto-calculates the claim from the medical expenses paid field below.",
    )
    medical_expenses_paid = number_input(
        "Medical Expenses Paid",
        "medical_expenses_paid",
        100.0,
        "For 2025, the estimator automatically subtracts the CRA threshold and uses the remaining eligible amount.",
    )
    charitable_donations = number_input("Charitable Donations", "charitable_donations", 100.0)
    additional_federal_credits = number_input(
        "Additional Federal Non-Refundable Claim Amount",
        "additional_federal_credits",
        100.0,
        "Enter additional federal claim amount bases from other CRA worksheets if needed.",
    )
    additional_provincial_credit_amount = number_input(
        f"Additional {province_name} Non-Refundable Credit",
        "additional_provincial_credit_amount",
        100.0,
        "Enter this as the final provincial credit amount in dollars.",
    )
    refundable_credits = number_input(
        "Other Manual Refundable Credits",
        "refundable_credits",
        100.0,
        "Use this for refundable credits not otherwise listed below.",
    )
    st.markdown("#### Refundable Credits Engine")
    refundable_col1, refundable_col2 = st.columns(2)
    canada_workers_benefit = refundable_col1.number_input(
        "Canada Workers Benefit Manual Override",
        min_value=0.0,
        step=100.0,
        value=float(st.session_state.get("canada_workers_benefit", 0.0)),
        key="canada_workers_benefit",
        help="Leave at 0 to use the app's estimate. Enter your own amount only if you are following the worksheet manually.",
    )
    cwb_disability_supplement_eligible = refundable_col1.checkbox(
        "Eligible for CWB Disability Supplement",
        value=bool(st.session_state.get("cwb_disability_supplement_eligible", False)),
        key="cwb_disability_supplement_eligible",
        help="Check this if the taxpayer is eligible for the disability tax credit and you want the app to include the CWB disability supplement in the 2025 auto estimate.",
    )
    spouse_cwb_disability_supplement_eligible = False
    if has_spouse_end_of_year:
        spouse_cwb_disability_supplement_eligible = refundable_col1.checkbox(
            "Spouse Also Eligible for CWB Disability Supplement",
            value=bool(st.session_state.get("spouse_cwb_disability_supplement_eligible", False)),
            key="spouse_cwb_disability_supplement_eligible",
            help="Used only for the family-income phaseout path in the app's 2025 disability-supplement estimate.",
        )
    canada_training_credit_limit_available = refundable_col1.number_input(
        "Canada Training Credit Limit Available",
        min_value=0.0,
        step=100.0,
        value=float(st.session_state.get("canada_training_credit_limit_available", 0.0)),
        key="canada_training_credit_limit_available",
        help="Used for automatic Canada Training Credit estimation against current-year tuition/training claims.",
    )
    canada_training_credit = refundable_col1.number_input(
        "Canada Training Credit Manual Override",
        min_value=0.0,
        step=100.0,
        value=float(st.session_state.get("canada_training_credit", 0.0)),
        key="canada_training_credit",
        help="Leave at 0 to use the app's estimate from the training credit limit and current-year tuition claim.",
    )
    medical_expense_supplement = refundable_col1.number_input(
        "Medical Expense Supplement Manual Override",
        min_value=0.0,
        step=100.0,
        value=float(st.session_state.get("medical_expense_supplement", 0.0)),
        key="medical_expense_supplement",
        help="Leave at 0 to use the app's estimate from employment income, net income, and the medical claim.",
    )
    other_federal_refundable_credits = refundable_col2.number_input(
        "Other Federal Refundable Credits",
        min_value=0.0,
        step=100.0,
        value=float(st.session_state.get("other_federal_refundable_credits", 0.0)),
        key="other_federal_refundable_credits",
    )
    manual_provincial_refundable_credits = refundable_col2.number_input(
        f"Other {province_name} Refundable Credits",
        min_value=0.0,
        step=100.0,
        value=float(st.session_state.get("manual_provincial_refundable_credits", 0.0)),
        key="manual_provincial_refundable_credits",
    )
    refundable_credits_engine_total = (
        canada_workers_benefit
        + canada_training_credit
        + medical_expense_supplement
        + other_federal_refundable_credits
        + manual_provincial_refundable_credits
        + refundable_credits
    )
    render_metric_row(
        [
            ("CWB Manual Override", canada_workers_benefit),
            ("CWB Disability Eligible", float(cwb_disability_supplement_eligible)),
            ("Training Credit Limit", canada_training_credit_limit_available),
            ("Medical Supplement Override", medical_expense_supplement),
        ],
        4,
    )
    st.caption("Automatic refundable estimates currently include Canada Workers Benefit, Canada Training Credit, Medical Expense Supplement, and CPP/EI overpayment refunds. These are added on top of any built-in province-specific refundable schedules such as MB479, NS479, NB(S12), or NL479.")
    st.markdown("#### Province-Specific Extra Credits")
    st.caption(
        "This section now carries province-aware inputs for caregiver and dependant-child style claims. "
        "Ontario still has the deepest built-in worksheet support, but other provinces now have more direct hooks too."
    )
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

    st.markdown("#### Foreign and Dividend Credits")
    fd_col1, fd_col2, fd_col3 = st.columns(3)
    foreign_income = number_input(
        "Manual Additional Foreign Non-Business Income",
        "foreign_income",
        100.0,
        "Use this only for foreign non-business income not already captured by T5, T3, or T4PS slips.",
    )
    foreign_tax_paid = number_input(
        "Manual Additional Foreign Tax Paid",
        "foreign_tax_paid",
        100.0,
        "Use this only for foreign tax paid not already captured by T5 or T3 slips.",
    )
    ontario_dividend_tax_credit_manual = number_input(
        f"{province_name} Dividend Tax Credit Override",
        "provincial_dividend_tax_credit_manual",
        50.0,
        f"Leave at 0 to use the auto-calculated {province_name} dividend tax credit where supported. Enter a higher amount only if your worksheet shows a different result.",
    )
    foreign_income += (
        float(t5_wizard_totals.get("box15_foreign_income", 0.0))
        + float(t3_wizard_totals.get("box25_foreign_income", 0.0))
        + float(t4ps_wizard_totals.get("box37_foreign_non_business_income", 0.0))
    )
    foreign_tax_paid += (
        float(t5_wizard_totals.get("box16_foreign_tax_paid", 0.0))
        + float(t3_wizard_totals.get("box34_foreign_tax_paid", 0.0))
    )
    st.caption(
        "Foreign income and foreign tax from T5, T3, and T4PS slips are added automatically. "
        "The manual fields above are for extra amounts not already in those slips."
    )

    st.markdown("#### T2209 / T2036 Worksheet")
    ftc_col1, ftc_col2, ftc_col3 = st.columns(3)
    t2209_non_business_tax_paid = number_input(
        "T2209 Line 1 Non-Business Tax Paid",
        "t2209_non_business_tax_paid",
        100.0,
        "If left at 0, the estimator falls back to Foreign Tax Paid.",
    )
    t2209_net_foreign_non_business_income = number_input(
        "T2209 Line 2 Net Foreign Non-Business Income",
        "t2209_net_foreign_non_business_income",
        100.0,
        "If left at 0, the estimator falls back to Foreign Non-Business Income.",
    )
    t2209_net_income_override = number_input(
        "T2209 Net Income Override",
        "t2209_net_income_override",
        100.0,
        "Optional override for the T2209 denominator if you are following the form exactly.",
    )
    t2209_basic_federal_tax_override = number_input(
        "T2209 Basic Federal Tax Override",
        "t2209_basic_federal_tax_override",
        100.0,
        "Optional override for the T2209 basic federal tax amount.",
    )
    t2036_provincial_tax_otherwise_payable_override = number_input(
        "T2036 Provincial Tax Otherwise Payable Override",
        "t2036_provincial_tax_otherwise_payable_override",
        100.0,
        "Optional override for the T2036 provincial tax otherwise payable amount.",
    )

    st.markdown("#### Schedule 9 Donations")
    don_col1, don_col2, don_col3 = st.columns(3)
    donations_eligible_total = number_input(
        "Schedule 9 Regular Donations",
        "donations_eligible_total",
        100.0,
        "Use this to model Schedule 9 more closely. If left at 0, Charitable Donations above will be used.",
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

    st.markdown("#### Carryforwards and Transfers")
    carryforward_tabs = st.tabs(["Tuition Carryforward", "Donation Carryforward", f"{province_name} Credit Lines"])
    with carryforward_tabs[0]:
        tuition_cf_df = render_record_card_editor(
            "Tuition Carryforward by Year",
            "tuition_carryforwards",
            [
                {"id": "tax_year", "label": "Tax Year", "step": 1.0},
                {"id": "available_amount", "label": "Available Amount", "step": 100.0},
                {"id": "claim_amount", "label": "Claim Amount", "step": 100.0},
            ],
            "Enter one row per carryforward year. Requested claims are capped to the available amount and flow into the Schedule 11 worksheet.",
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
            "Enter one row per donation carryforward year. Claim amounts are added to Schedule 9 regular donations.",
        )
    with carryforward_tabs[2]:
        provincial_credit_lines_df = render_record_card_editor(
            f"{province_name} Additional Credit Lines",
            "provincial_credit_lines",
            [
                {"id": "line_code", "label": "Line Code", "step": 1.0},
                {"id": "amount", "label": "Amount", "step": 100.0},
            ],
            "Use this for province-specific credit lines not otherwise modelled. Amounts are added to provincial non-refundable credits.",
        )
    tuition_cf_preview_df = coerce_editor_df(tuition_cf_df.copy(), ["tax_year", "available_amount", "claim_amount"])
    donation_cf_preview_df = coerce_editor_df(donation_cf_df.copy(), ["tax_year", "available_amount", "claim_amount"])
    provincial_credit_lines_preview_df = coerce_editor_df(provincial_credit_lines_df.copy(), ["line_code", "amount"])
    tuition_carryforward_used_preview = min(
        float(tuition_cf_preview_df["available_amount"].sum()),
        float(tuition_cf_preview_df["claim_amount"].sum()),
    )
    render_metric_row(
        [
            ("Tuition Carryforward Used", tuition_carryforward_used_preview),
            ("Donation Carryforward Used", min(float(donation_cf_preview_df["available_amount"].sum()), float(donation_cf_preview_df["claim_amount"].sum()))),
            (f"{province_name} Extra Credit Lines", float(provincial_credit_lines_preview_df["amount"].sum())),
        ],
        3,
    )

    st.markdown("#### Province Special Schedules")
    st.caption(
        "These fields map to province-specific schedules and special credits. Where the CRA form has a complex worksheet, "
        "the app uses either a focused estimator or a final-credit input so the result still flows into refund or balance owing."
    )
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
        volunteer_flag = st.checkbox(
            "NS479 Volunteer Firefighter / Search and Rescue Credit",
            value=bool(st.session_state.get("ns479_volunteer_flag", False)),
            key="ns479_volunteer_flag",
            help="If eligible, the app enters the fixed $500 NS479 credit.",
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
        bc_renters_credit_eligible = sp_col1.checkbox(
            "BC Renter's Tax Credit Eligible",
            value=bool(st.session_state.get("bc_renters_credit_eligible", False)),
            key="bc_renters_credit_eligible",
            help="Check if the taxpayer qualifies to claim the B.C. renter's tax credit.",
        )
        bc_home_renovation_eligible = sp_col2.checkbox(
            "BC Home Renovation Credit Eligible",
            value=bool(st.session_state.get("bc_home_renovation_eligible", False)),
            key="bc_home_renovation_eligible",
            help="Check if the taxpayer or qualifying household qualifies for the B.C. home renovation credit.",
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
        pe_volunteer_credit_eligible = sp_col1.checkbox(
            "PE Volunteer Firefighter / Search and Rescue Credit Eligible",
            value=bool(st.session_state.get("pe_volunteer_credit_eligible", False)),
            key="pe_volunteer_credit_eligible",
            help="Check if the taxpayer qualifies for the Prince Edward Island volunteer firefighter or volunteer search and rescue personnel tax credit.",
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

with st.expander("5) Payments and Withholdings (Optional)", expanded=False):
    st.caption("You can skip this section unless you made instalments, had extra tax deducted outside slips, or need to add other payments not already captured from your slips.")
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

with st.expander("Pre-Calculation Diagnostics", expanded=bool(diagnostics)):
    if diagnostics:
        render_diagnostics_panel(diagnostics)
    else:
        st.caption("No obvious duplication or consistency issues were detected from the current inputs.")

action_col1, action_col2, action_col3 = st.columns([1.2, 0.7, 4.1])
with action_col1:
    calculate_clicked = st.button("Calculate Return", type="primary", use_container_width=True)
with action_col2:
    reset_clicked = st.button("Reset", use_container_width=True)

if reset_clicked:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

if calculate_clicked:
    result = calculate_personal_tax_return(
        {
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
            "spouse_claim_enabled": spouse_claim_enabled,
            "spouse_infirm": spouse_infirm,
            "has_spouse_end_of_year": has_spouse_end_of_year,
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
    )
    postcalc_diagnostics = collect_postcalc_diagnostics(result)
    st.session_state["tax_result"] = result

if "tax_result" in st.session_state:
    result = st.session_state["tax_result"]
    postcalc_diagnostics = collect_postcalc_diagnostics(result)

    st.subheader("6) Results")
    provincial_form_code = PROVINCIAL_FORM_CODES.get(province, "428")
    tab_names = ["Client Summary", "Return", "Reconciliation", "T2209", provincial_form_code, "T776", "Schedule 3", "Schedule 11", "Schedule 9", "Scope / Limits"]
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
        st.markdown("#### Client Summary")
        render_metric_row(
            [
                ("Total Income", result["total_income"]),
                ("Taxable Income", result["taxable_income"]),
                ("Total Payable", result["total_payable"]),
                ("Income Tax Withheld", result["income_tax_withheld"]),
            ],
            4,
        )
        if result["line_48400_refund"] > 0:
            st.info(
                f"This estimate currently shows an expected refund of {format_currency(result['line_48400_refund'])}. "
                f"That result is based on the slips, deductions, credits, and payments entered so far."
            )
        elif result["line_48500_balance_owing"] > 0:
            st.warning(
                f"This estimate currently shows a balance owing of {format_currency(result['line_48500_balance_owing'])}. "
                f"That usually means total payable is higher than withholding, instalments, and refundable credits."
            )
        else:
            st.caption("The current estimate is roughly balanced, with little or no refund or balance owing.")

        client_drivers_df = build_client_key_drivers_df(result, province_name)
        readiness_df = build_filing_readiness_df(
            result=result,
            diagnostics=diagnostics,
            postcalc_diagnostics=postcalc_diagnostics,
            province=province,
            province_name=province_name,
        )
        with st.expander("Client Review Details", expanded=False):
            st.markdown("#### Plain-Language Summary")
            st.dataframe(build_client_summary_df(result, province_name), use_container_width=True, hide_index=True)
            st.markdown("#### Main Factors Affecting The Result")
            if client_drivers_df.empty:
                st.caption("No major deductions, credits, or payment drivers are standing out yet.")
            else:
                st.dataframe(client_drivers_df, use_container_width=True, hide_index=True)
            st.markdown("#### Filing-Readiness Checklist")
            render_filing_readiness_panel(readiness_df)
        printable_html = build_printable_client_summary_html(result, province_name, readiness_df, client_drivers_df, include_cta=False)
        printable_pdf = build_printable_client_summary_pdf(result, province_name, readiness_df, client_drivers_df)
        with st.expander("Printable Client Summary", expanded=False):
            st.markdown(printable_html, unsafe_allow_html=True)
            st.download_button(
                "Download Client Summary (PDF)",
                data=printable_pdf,
                file_name=f"{province_name.lower().replace(' ', '-')}-tax-estimate-summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        st.caption("This view is written in simpler language for sharing or review. The detailed worksheet tabs remain available for preparer-style tracing.")

    with return_tab:
        detail_col1, detail_col2 = st.columns(2)
        with detail_col1:
            st.markdown("#### Return Summary")
            summary_df = build_summary_df(result)
            st.dataframe(
                summary_df.assign(Amount=summary_df["Amount"].map(format_currency)),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("#### Line-by-Line Return Summary")
            line_df = line_summary_df(result, province_name)
            line_df["Amount"] = line_df["Amount"].map(format_currency)
            st.dataframe(line_df, use_container_width=True, hide_index=True)
            st.markdown("#### Return Package Summary")
            package_df = build_return_package_df(result, province_name)
            st.dataframe(package_df, use_container_width=True, hide_index=True)

        with detail_col2:
            st.markdown("#### Credits and Deductions")
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

    with reconciliation_tab:
        st.markdown("#### Slip Reconciliation")
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
        )
        render_reconciliation_panel(reconciliation_df)
        st.caption("This view compares wizard slip totals, manual extra inputs, and the final return amounts used by the app. Non-zero differences usually mean there is an override, a cap, or an allocation rule affecting the final return.")

        st.markdown("#### Assumptions and Overrides Summary")
        assumptions_df = build_assumptions_overrides_df(
            result=result,
            province_name=province_name,
            tuition_claim_override=tuition_amount_claim,
            t2209_net_income_override=t2209_net_income_override,
            t2209_basic_federal_tax_override=t2209_basic_federal_tax_override,
            t2036_provincial_tax_otherwise_payable_override=t2036_provincial_tax_otherwise_payable_override,
        )
        render_assumptions_overrides_panel(assumptions_df)
        st.caption("This table highlights where the app used a manual override, an automatic estimate, or a cap/allocation rule instead of a straight slip-to-line mapping.")

        st.markdown("#### Missing-Support Checklist")
        missing_support_df = build_missing_support_df(result, province, province_name)
        st.dataframe(missing_support_df, use_container_width=True, hide_index=True)
        st.caption("This checklist points to the slips, receipts, and worksheet support that would normally be worth reviewing before treating the estimate as filing-ready.")

        st.markdown("#### Filing-Readiness Detail")
        render_filing_readiness_panel(readiness_df)
        st.caption("Use this view as a quick preparer workflow check: `Ready` means the section looks supportable, `Review` means it likely needs human confirmation, and `Missing` means a blocking issue is still showing.")

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
        st.markdown("#### T2209 / T2036 Worksheet View")
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
        st.dataframe(t2209_rows, use_container_width=True, hide_index=True)

    with provincial_tab:
        st.markdown(f"#### {province_name} Worksheet View")
        provincial_rows = build_provincial_worksheet_df(result, province, province_name)
        provincial_rows["Amount"] = provincial_rows["Amount"].map(format_currency)
        st.dataframe(provincial_rows, use_container_width=True, hide_index=True)

    with t776_tab:
        st.markdown("#### T776 Worksheet View")
        t776_rows = build_t776_df(result)
        t776_rows["Amount"] = t776_rows["Amount"].map(format_currency)
        st.dataframe(t776_rows, use_container_width=True, hide_index=True)

    with s3_tab:
        st.markdown("#### Schedule 3 Worksheet View")
        s3_rows = build_schedule_3_df(result)
        s3_rows["Amount"] = s3_rows["Amount"].map(format_currency)
        st.dataframe(s3_rows, use_container_width=True, hide_index=True)

    with s11_tab:
        st.markdown("#### Schedule 11 Worksheet View")
        s11_rows = build_schedule_11_df(result)
        s11_rows["Amount"] = s11_rows["Amount"].map(format_currency)
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
        st.dataframe(s9_rows, use_container_width=True, hide_index=True)

    with scope_tab:
        st.markdown("#### Supported Scope")
        st.markdown(read_public_markdown_doc("PUBLIC_SUPPORTED_SCOPE.md"))
        st.markdown("#### Best-Fit And Manual Review Scenarios")
        st.markdown(read_public_markdown_doc("PUBLIC_BEST_FIT_AND_REVIEW_SCENARIOS.md"))
        st.markdown("#### Limitations and Boundaries")
        st.markdown(read_public_markdown_doc("PUBLIC_LIMITATIONS.md"))
        st.caption("This page summarizes the current supported T1 scope, public-safe positioning, and the practical boundaries that still matter when using or presenting the app.")

    if special_tab is not None:
        with special_tab:
            st.markdown(f"#### {special_tab_name} Worksheet View")
            special_rows = build_special_schedule_df(result, province)
            if special_rows.empty:
                st.caption("No additional province-specific rows are available for this province yet.")
            else:
                special_rows["Amount"] = special_rows["Amount"].map(format_currency)
                st.dataframe(special_rows, use_container_width=True, hide_index=True)

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

    with st.expander("Household Review", expanded=False):
        render_household_review_panel(result)

    with st.expander("Post-Calculation Diagnostics", expanded=bool(postcalc_diagnostics)):
        if postcalc_diagnostics:
            render_diagnostics_panel(postcalc_diagnostics)
        else:
            st.caption("No obvious refundable-credit or payment-allocation issues were detected after calculation.")

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

    with st.expander("CPP / EI Breakdown"):
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

    with st.expander("Tax Formula Notes"):
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

st.markdown("---")
st.caption(
    "This estimator is much broader than the original employment-only calculator, but it is still not a substitute "
    "for CRA-certified filing software. Review slip amounts, carryforwards, and province-specific credits carefully."
)
