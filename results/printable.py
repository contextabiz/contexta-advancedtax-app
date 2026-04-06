from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .client_summary import build_client_summary_cta, build_client_summary_notes


def build_printable_client_summary_html(
    result: dict,
    province_name: str,
    readiness_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    *,
    format_currency,
    include_cta: bool = True,
) -> str:
    notes = build_client_summary_notes(
        result,
        readiness_df,
        province_name,
        format_currency=format_currency,
    )
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
    *,
    format_currency,
    logo_path: Path,
) -> bytes:
    notes = build_client_summary_notes(
        result,
        readiness_df,
        province_name,
        format_currency=format_currency,
    )
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
    divider_y = min(y - 8, baseline_y - 8 if "baseline_y" in locals() else y - 8)
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
