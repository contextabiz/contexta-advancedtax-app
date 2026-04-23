from rule_engine import SimpleDiagnosticRule, value


CARRYFORWARD_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Warning",
        "category": "Carryforward",
        "message": "Tuition carryforward claimed exceeds the available amount. The app caps the claim, but you should review the carryforward rows.",
        "when": lambda data: value(data, "tuition_carryforward_claim_requested") > value(data, "tuition_carryforward_available_total"),
    },
    {
        "severity": "Warning",
        "category": "Carryforward",
        "message": "Donation carryforward claimed exceeds the available amount. Review the carryforward rows.",
        "when": lambda data: value(data, "donation_carryforward_claim_requested") > value(data, "donation_carryforward_available_total"),
    },
    {
        "severity": "Info",
        "category": "Schedule 9",
        "message": "Total regular donations requested exceed the app's 75% of net income preview limit. The app will cap current-year and carryforward usage in the final Schedule 9 flow.",
        "when": lambda data: value(data, "schedule9_regular_limit_preview") < (
            value(data, "schedule9_current_year_donations_claim_requested")
            + value(data, "donation_carryforward_claim_requested")
        ),
    },
    {
        "severity": "Info",
        "category": "Schedule 9",
        "message": "Ecological or cultural gifts are entered. The app treats these as outside the normal 75% of net income limit, consistent with CRA guidance.",
        "when": lambda data: value(data, "ecological_cultural_gifts") > 0,
    },
    {
        "severity": "Info",
        "category": "Carryforward",
        "message": "Requested net capital loss carryforward exceeds current taxable capital gains. The app only uses the amount that can be applied this year.",
        "when": lambda data: value(data, "net_capital_loss_carryforward") > value(data, "taxable_capital_gains"),
    },
]


POSTCALC_CARRYFORWARD_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Schedule 9",
        "message": "Donation carryforward requested exceeds the amount used in the final Schedule 9 flow. The app capped the carryforward claim to the available amount.",
        "when": lambda data: value(data, "schedule9_carryforward_claim_requested") > value(data, "schedule9_carryforward_claim_used"),
    },
    {
        "severity": "Info",
        "category": "Schedule 9",
        "message": "Donations above $200 were claimed, but no high-rate donation portion was produced. This can be correct if taxable income did not exceed the federal high-rate threshold.",
        "when": lambda data: value(data, "donation_high_rate_portion") == 0
        and value(data, "schedule9_total_regular_donations_claimed") > 200
        and value(data, "taxable_income") > 0,
    },
    {
        "severity": "Info",
        "category": "Schedule 9",
        "message": "Cultural or ecological gifts were included outside the regular 75% donation limit. Review line 34200 support if you are matching a CRA worksheet manually.",
        "when": lambda data: value(data, "schedule9_unlimited_gifts_claimed") > 0,
    },
]
