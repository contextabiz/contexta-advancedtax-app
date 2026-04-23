from rule_engine import SimpleDiagnosticRule, flag, text, value


PROVINCIAL_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Warning",
        "category": "Provincial refundable credits",
        "message": "Ontario seniors' public transit expenses are entered, but age is under 65.",
        "when": lambda data: text(data, "province") == "ON" and value(data, "ontario_seniors_public_transit_expenses") > 0 and value(data, "age") < 65,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "B.C. home renovation expenses are entered, but the eligibility checkbox is not selected.",
        "when": lambda data: text(data, "province") == "BC" and value(data, "bc_home_renovation_expenses") > 0 and not flag(data, "bc_home_renovation_eligible"),
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "B.C. renter's credit eligibility is checked and manual provincial refundable credits are also entered. Review for duplication.",
        "when": lambda data: text(data, "province") == "BC"
        and flag(data, "bc_renters_credit_eligible")
        and flag(data, "has_spouse_end_of_year")
        and value(data, "manual_provincial_refundable_credits") > 0,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "Saskatchewan fertility treatment expenses exceed $20,000. The app caps the refundable credit at the Saskatchewan maximum.",
        "when": lambda data: text(data, "province") == "SK" and value(data, "sk_fertility_treatment_expenses") > 20000,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "Prince Edward Island volunteer credit eligibility is checked and manual provincial refundable credits are also entered. Review for duplication.",
        "when": lambda data: text(data, "province") == "PE"
        and flag(data, "pe_volunteer_credit_eligible")
        and value(data, "manual_provincial_refundable_credits") > 0,
    },
]


POSTCALC_PROVINCIAL_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "Ontario seniors' public transit expenses were entered, but no Ontario seniors' transit credit was produced. This can be correct if the age requirement is not met.",
        "when": lambda data: value(data, "ontario_seniors_public_transit_expenses") > 0 and value(data, "ontario_seniors_transit_credit") == 0,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "B.C. renter's credit eligibility is checked, but no B.C. renter's credit was produced. Review adjusted family net income and renter eligibility.",
        "when": lambda data: value(data, "bc_renters_credit_eligible") > 0 and value(data, "bc_renters_credit") == 0,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "B.C. home renovation expenses were entered, but no B.C. home renovation credit was produced. Review the eligibility checkbox.",
        "when": lambda data: value(data, "bc_home_renovation_expenses") > 0 and value(data, "bc_home_renovation_credit") == 0,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "Saskatchewan fertility treatment expenses were entered, but no Saskatchewan fertility credit was produced. Review province selection and eligible-expense entry.",
        "when": lambda data: value(data, "sk_fertility_treatment_expenses") > 0 and value(data, "sk_fertility_credit") == 0,
    },
    {
        "severity": "Info",
        "category": "Provincial refundable credits",
        "message": "P.E.I. volunteer credit eligibility is checked, but no P.E.I. volunteer credit was produced. Review the PE428 volunteer-credit input.",
        "when": lambda data: value(data, "pe_volunteer_credit_eligible") > 0 and value(data, "pe_volunteer_credit") == 0,
    },
]
