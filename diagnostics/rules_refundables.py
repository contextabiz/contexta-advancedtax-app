from rule_engine import SimpleDiagnosticRule, flag, value


REFUNDABLE_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "A manual Canada Workers Benefit override is entered. The app will use your manual amount instead of the automatic estimate.",
        "when": lambda data: value(data, "canada_workers_benefit_manual") > 0 and value(data, "canada_workers_benefit_auto") > 0,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "Canada Workers Benefit is present, but working income is at or below the basic working-income threshold. Review eligibility.",
        "when": lambda data: value(data, "estimated_working_income") <= 3000 and (
            value(data, "canada_workers_benefit_manual") > 0 or value(data, "canada_workers_benefit_auto") > 0
        ),
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "Spouse CWB disability supplement eligibility is checked, but 'Had Spouse at Year End' is not checked.",
        "when": lambda data: flag(data, "spouse_cwb_disability_supplement_eligible") and not flag(data, "has_spouse_end_of_year"),
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "A Canada Training Credit override is entered, but the training credit limit available is zero.",
        "when": lambda data: value(data, "canada_training_credit_manual") > 0 and value(data, "canada_training_credit_limit_available") == 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "Canada Training Credit override exceeds the limit available entered. Review the training credit worksheet.",
        "when": lambda data: value(data, "canada_training_credit_manual") > value(data, "canada_training_credit_limit_available")
        and value(data, "canada_training_credit_limit_available") > 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "A manual Medical Expense Supplement override is entered. The app will use your manual amount instead of the automatic estimate.",
        "when": lambda data: value(data, "medical_expense_supplement_manual") > 0 and value(data, "medical_expense_supplement_auto") > 0,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "Medical Expense Supplement is entered, but employment income is below the usual earned-income threshold.",
        "when": lambda data: value(data, "medical_expense_supplement_manual") > 0 and value(data, "estimated_working_income") < 4275,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "Medical Expense Supplement is present, but no medical claim amount is currently available.",
        "when": lambda data: (
            value(data, "medical_expense_supplement_manual") > 0 or value(data, "medical_expense_supplement_auto") > 0
        ) and value(data, "medical_claim_amount") == 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "CPP withheld on slips appears higher than the app's employee CPP estimate. A CPP overpayment refund estimate will be added automatically.",
        "when": lambda data: value(data, "cpp_overpayment_refund_auto") > 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "EI withheld on slips appears higher than the app's EI estimate. An EI overpayment refund estimate will be added automatically.",
        "when": lambda data: value(data, "ei_overpayment_refund_auto") > 0,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "CPP withheld is entered, but employment income is zero. Review whether a T4 employment amount is missing.",
        "when": lambda data: value(data, "cpp_withheld_total") > 0 and value(data, "estimated_working_income") == 0,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "EI withheld is entered, but employment income is zero. Review whether a T4 employment amount is missing.",
        "when": lambda data: value(data, "ei_withheld_total") > 0 and value(data, "estimated_working_income") == 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "Manual refundable credits and province-specific refundable schedule credits are both present. Confirm you are not duplicating refundable claims.",
        "when": lambda data: value(data, "manual_refundable_credits_total") > 0 and value(data, "provincial_special_refundable_credits") > 0,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "Refundable credits are entered while total income is zero. Review whether the refundable claims belong in this return.",
        "when": lambda data: value(data, "manual_refundable_credits_total") > 0 and value(data, "estimated_total_income") == 0,
    },
]


POSTCALC_REFUNDABLE_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "Total refundable credits exceed total payable. This can be valid, but the refund result is now being driven mainly by refundable items.",
        "when": lambda data: value(data, "refundable_credits") > value(data, "total_payable") and value(data, "total_payable") > 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "More than half of the refund/payout is being driven by refundable credits. Review override inputs and provincial refundable schedules carefully.",
        "when": lambda data: value(data, "line_48400_refund") > 0
        and value(data, "refundable_credits") > 0
        and value(data, "refundable_credits") >= max(1.0, value(data, "total_payments") * 0.5),
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "The return shows a refund even though no income tax was withheld, which means the result is being driven by refundable credits only.",
        "when": lambda data: value(data, "income_tax_withheld") == 0 and value(data, "refundable_credits") > 0 and value(data, "line_48400_refund") > 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "Manual provincial refundable credits and built-in provincial refundable schedules are both present in the final result. Check that the same provincial credit was not counted twice.",
        "when": lambda data: value(data, "manual_provincial_refundable_credits") > 0 and value(data, "provincial_special_refundable_credits") > 0,
    },
]
