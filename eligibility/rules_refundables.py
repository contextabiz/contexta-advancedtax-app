from rule_engine import DecisionDiagnosticRule, SimpleDiagnosticRule, review_flag, rule_present, value


ELIGIBILITY_REFUNDABLE_RULES: list[DecisionDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "CWB has already been flagged for review. If the amount still looks off, check working income, family-income range, and any Schedule 6 restrictions.",
        "message_from_rule_id": None,
        "when": lambda context, decision, rule_result_by_id: rule_present(rule_result_by_id, "cwb_enabled")
        and value(context, "canada_workers_benefit_auto") == 0
        and value(context, "canada_workers_benefit_manual") == 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": None,
        "message_from_rule_id": "cwb_disability_requires_basic_cwb",
        "when": lambda context, decision, rule_result_by_id: review_flag(decision, "cwb_disability_requires_basic_cwb"),
    },
]


ELIGIBILITY_POSTCALC_REFUNDABLE_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "Manual Canada Workers Benefit override differs materially from the app's auto estimate. Review the CWB worksheet if you entered the amount manually.",
        "when": lambda result: value(result, "canada_workers_benefit_manual") > 0
        and abs(value(result, "canada_workers_benefit_manual") - value(result, "canada_workers_benefit_auto")) > 100.0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "The app calculated a positive Canada Workers Benefit estimate, but it was not used. Review whether a manual override or another input suppressed it.",
        "when": lambda result: value(result, "canada_workers_benefit") == 0 and value(result, "canada_workers_benefit_auto") > 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "The final Canada Workers Benefit includes a disability supplement estimate.",
        "when": lambda result: value(result, "cwb_disability_supplement_auto") > 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "A manual Canada Workers Benefit override is being used while CWB disability supplement eligibility is checked. Review whether the manual total already includes the supplement.",
        "when": lambda result: value(result, "cwb_disability_supplement_eligible") > 0 and value(result, "canada_workers_benefit_manual") > 0,
    },
    {
        "severity": "Warning",
        "category": "Refundable credits",
        "message": "Manual Canada Training Credit exceeds the training credit limit available entered. The app used the manual override, so review the Schedule 11 / training-credit worksheet.",
        "when": lambda result: value(result, "canada_training_credit_manual") > 0
        and value(result, "canada_training_credit_limit_available") > 0
        and value(result, "canada_training_credit_manual") > value(result, "canada_training_credit_limit_available"),
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "A training credit limit is available, but no current-year tuition/training claim was used. The automatic Canada Training Credit therefore stayed at zero.",
        "when": lambda result: value(result, "canada_training_credit_auto") == 0
        and value(result, "canada_training_credit_limit_available") > 0
        and value(result, "schedule11_current_year_claim_used") == 0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "Manual Medical Expense Supplement override differs materially from the app's auto estimate. Review the supplement worksheet if you entered it manually.",
        "when": lambda result: value(result, "medical_expense_supplement_manual") > 0
        and abs(value(result, "medical_expense_supplement_manual") - value(result, "medical_expense_supplement_auto")) > 100.0,
    },
    {
        "severity": "Info",
        "category": "Refundable credits",
        "message": "A federal medical claim exists, but no Medical Expense Supplement was produced. This can be correct if income thresholds are not met.",
        "when": lambda result: value(result, "medical_expense_supplement_auto") == 0
        and value(result, "medical_expense_supplement") == 0
        and value(result, "federal_medical_claim") > 0,
    },
]


ELIGIBILITY_POSTCALC_PAYROLL_RULES: list[SimpleDiagnosticRule] = [
    {
        "severity": "Info",
        "category": "Payroll refund",
        "message": "CPP withheld on slips is above the app's employee CPP estimate, so a CPP overpayment refund estimate was included.",
        "when": lambda result: value(result, "cpp_overpayment_refund") > 0,
    },
    {
        "severity": "Info",
        "category": "Payroll refund",
        "message": "EI withheld on slips is above the app's EI estimate, so an EI overpayment refund estimate was included.",
        "when": lambda result: value(result, "ei_overpayment_refund") > 0,
    },
]
