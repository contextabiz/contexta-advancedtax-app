from rule_engine import SimpleDiagnosticRule, value


FOREIGN_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Warning",
        "category": "Duplicate input",
        "message": "Manual foreign income and slip-based foreign income are both entered. Confirm the manual amount is only for extra foreign income not on T5/T3/T4PS.",
        "when": lambda data: value(data, "manual_foreign_income") > 0 and value(data, "slip_foreign_income_total") > 0,
    },
    {
        "severity": "Warning",
        "category": "Duplicate input",
        "message": "Manual foreign tax paid and slip-based foreign tax paid are both entered. Confirm the manual amount is only for extra foreign tax not already on slips.",
        "when": lambda data: value(data, "manual_foreign_tax_paid") > 0 and value(data, "slip_foreign_tax_paid_total") > 0,
    },
    {
        "severity": "High",
        "category": "Foreign tax",
        "message": "Foreign tax paid is entered, but foreign income is zero. T2209/T2036 usually need foreign income to support the credit.",
        "when": lambda data: value(data, "foreign_tax_paid_total") > 0 and value(data, "foreign_income_total") == 0,
    },
    {
        "severity": "High",
        "category": "Foreign tax",
        "message": "T2209 tax paid is entered, but T2209 net foreign non-business income is zero.",
        "when": lambda data: value(data, "t2209_non_business_tax_paid") > 0 and value(data, "t2209_net_foreign_non_business_income") == 0,
    },
    {
        "severity": "Warning",
        "category": "Foreign tax",
        "message": "T2209 net income override is lower than foreign non-business income. Review the worksheet override.",
        "when": lambda data: value(data, "t2209_net_income_override") > 0 and value(data, "t2209_net_income_override") < value(data, "t2209_net_foreign_non_business_income"),
    },
]
