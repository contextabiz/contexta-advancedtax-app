import streamlit as st

from .types import DiagnosticItem


def render_diagnostics_panel(
    checks: list[DiagnosticItem],
    *,
    formatter=None,
) -> None:
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

    if formatter is None:
        def formatter(value: float) -> str:
            return str(value)

    metric_values = [
        ("High-Risk", float(severity_counts["High"])),
        ("Warnings", float(severity_counts["Warning"])),
        ("Info", float(severity_counts["Info"])),
    ]
    columns = st.columns(3)
    for column, (label, value) in zip(columns, metric_values):
        display_value = formatter(value)
        column.metric(label, display_value)

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
