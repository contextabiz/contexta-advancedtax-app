from rule_engine import SimpleDiagnosticRule, value


INCOME_INPUT_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Warning",
        "category": "Duplicate input",
        "message": "Manual employment income and T4 Box 14 income are both entered. Confirm you are not counting the same employment income twice.",
        "when": lambda data: value(data, "employment_income_manual") > 0 and value(data, "t4_income_total") > 0,
    },
    {
        "severity": "Warning",
        "category": "Duplicate input",
        "message": "Manual pension income and slip-based pension income are both entered. Check that line 11500/11600 income is not duplicated.",
        "when": lambda data: value(data, "pension_income_manual") > 0 and (
            value(data, "t4a_pension_total") > 0 or value(data, "t3_pension_total") > 0
        ),
    },
    {
        "severity": "Warning",
        "category": "Duplicate input",
        "message": "Manual additional net rental income and T776 property income are both entered. Confirm the manual amount is truly separate.",
        "when": lambda data: value(data, "manual_net_rental_income") > 0 and value(data, "t776_net_rental_income") > 0,
    },
    {
        "severity": "Warning",
        "category": "Duplicate input",
        "message": "Manual additional taxable capital gains and Schedule 3 gains are both entered. Confirm the manual amount is not already in the Schedule 3 cards.",
        "when": lambda data: value(data, "manual_taxable_capital_gains") > 0 and value(data, "schedule3_taxable_capital_gains") > 0,
    },
    {
        "severity": "Info",
        "category": "Tuition",
        "message": "A current-year tuition override is entered while T2202 tuition is also available. This is okay if you are intentionally following Schedule 11 manually.",
        "when": lambda data: value(data, "tuition_amount_claim_override") > 0 and value(data, "t2202_tuition_total") > 0,
    },
    {
        "severity": "High",
        "category": "Likely missing slip",
        "message": "T4 income tax deducted is entered, but T4 Box 14 employment income is zero. Review the T4 wizard.",
        "when": lambda data: value(data, "t4_tax_withheld_total") > 0 and value(data, "t4_income_total") == 0,
    },
    {
        "severity": "High",
        "category": "Likely missing slip",
        "message": "T4 CPP/EI amounts are entered, but T4 employment income is zero. Review the T4 wizard.",
        "when": lambda data: (
            value(data, "t4_cpp_total") > 0 or value(data, "t4_ei_total") > 0
        ) and value(data, "t4_income_total") == 0,
    },
    {
        "severity": "Warning",
        "category": "Likely missing slip",
        "message": "T2202 months are entered, but eligible tuition is zero. Check T2202 Box 23/26.",
        "when": lambda data: value(data, "t2202_months_total") > 0 and value(data, "t2202_tuition_total") == 0,
    },
    {
        "severity": "High",
        "category": "Likely missing income",
        "message": "Income tax deducted at source is entered, but total income is zero. You may be missing a slip or income amount.",
        "when": lambda data: value(data, "income_tax_withheld_total") > 0 and value(data, "estimated_total_income") == 0,
    },
]


WITHHOLDING_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Withholding",
        "message": "Manual other tax deducted at source and slip-based tax deducted are both entered. This can be correct, but check line 43700 is not duplicated.",
        "when": lambda data: value(data, "income_tax_withheld_manual") > 0 and (
            value(data, "t4_tax_withheld_total") > 0 or value(data, "t4a_tax_withheld_total") > 0
        ),
    },
    {
        "severity": "Info",
        "category": "Withholding",
        "message": "T4 Box 24 EI insurable earnings differ materially from the estimator's EI base assumption.",
        "when": lambda data: value(data, "t4_box24_total") > 0 and abs(value(data, "t4_box24_total") - value(data, "estimator_ei_insurable_earnings")) > 100.0,
    },
    {
        "severity": "Info",
        "category": "Withholding",
        "message": "T4 Box 26 CPP pensionable earnings differ materially from the estimator's CPP base assumption.",
        "when": lambda data: value(data, "t4_box26_total") > 0 and abs(value(data, "t4_box26_total") - value(data, "estimator_cpp_pensionable_earnings")) > 100.0,
    },
]
