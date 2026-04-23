from rule_engine import SimpleDiagnosticRule, flag, text


HOUSEHOLD_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "High",
        "category": "Household",
        "message": "Spouse amount and eligible dependant are both selected. In many cases these cannot both be claimed together.",
        "when": lambda data: flag(data, "spouse_claim_enabled") and flag(data, "eligible_dependant_claim_enabled"),
    },
    {
        "severity": "Warning",
        "category": "Household",
        "message": "Spouse amount is selected while 'Separated in Year' is checked. Review whether the spouse amount should still be claimed.",
        "when": lambda data: flag(data, "spouse_claim_enabled") and flag(data, "separated_in_year"),
    },
    {
        "severity": "Warning",
        "category": "Household",
        "message": "Eligible dependant is selected, but 'Dependant Lived With You' is not checked.",
        "when": lambda data: flag(data, "eligible_dependant_claim_enabled") and not flag(data, "dependant_lived_with_you"),
    },
    {
        "severity": "High",
        "category": "Household",
        "message": "Eligible dependant is selected, but the dependant relationship is marked as 'Other'.",
        "when": lambda data: flag(data, "eligible_dependant_claim_enabled") and text(data, "dependant_relationship") == "Other",
    },
    {
        "severity": "High",
        "category": "Household",
        "message": "Eligible dependant is selected, but the dependant category is marked as 'Other'.",
        "when": lambda data: flag(data, "eligible_dependant_claim_enabled") and text(data, "dependant_category") == "Other",
    },
]
