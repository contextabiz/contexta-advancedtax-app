PLANNING_PRIORITY_THRESHOLDS = {
    "high_balance_owing": 1500.0,
    "spouse_low_income_upper": 16000.0,
    "material_tuition_room": 1000.0,
    "light_deduction_usage": 5000.0,
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

STEP5_CHECKPOINT_SHORT_BODIES = {
    "Possible spouse amount review": "Check spouse net income and whether line 30300 should be worked through here.",
    "Unused tuition room still showing": "Review available tuition, requested amount, and any carryforward before leaving Step 5.",
    "Deduction review may still reduce the balance owing": "If tax is still high, review RRSP, FHSA, child care, moving, support, and work deductions first.",
    "Refundable support may still be worth checking": "Confirm whether CWB, the disability supplement path, or the medical expense supplement should be opened.",
    "Medical or donation credits may still be underused": "Open this only if medical expenses or donations were not fully entered yet.",
    "Foreign tax inputs may still need positioning": "Recheck foreign income and tax paid only if those amounts apply on this return.",
}

STEP5_STATUS_BADGE_STYLES = {
    "Already active": {"bg": "rgba(38, 137, 83, 0.18)", "fg": "#9EE6BE", "border": "rgba(38, 137, 83, 0.28)"},
    "Looks underused": {"bg": "rgba(94, 166, 255, 0.16)", "fg": "#D8E9FF", "border": "rgba(94, 166, 255, 0.28)"},
    "Probably skip": {"bg": "rgba(143, 168, 198, 0.12)", "fg": "#B8C7D9", "border": "rgba(143, 168, 198, 0.18)"},
    "Review if applicable": {"bg": "rgba(192, 144, 60, 0.16)", "fg": "#F0D8A3", "border": "rgba(192, 144, 60, 0.24)"},
}

STEP5_SECTION_COPY = {
    "common_credits": {
        "status": "Probably skip",
        "why": "Open this if you paid tuition, student loan interest, medical expenses, or donations, or if a common non-refundable claim still needs input.",
        "note": "Nothing obvious is standing out yet from the current Step 5 entries.",
    },
    "household": {
        "status": "Probably skip",
        "why": "Open this if spouse, dependant, caregiver, support, or disability-transfer facts could change which household claim is supportable.",
        "note": "No household facts are standing out yet from the current inputs.",
    },
    "manual_overrides": {
        "status": "Probably skip",
        "why": "Open this only if you already have a worksheet amount or need to override the auto estimate.",
        "note": "For most returns, this can stay closed.",
    },
    "refundable": {
        "status": "Probably skip",
        "why": "Open this if lower-income support, CWB, training credit, or the medical expense supplement could still change the result.",
        "note": "No refundable-credit signal is standing out yet.",
    },
    "foreign": {
        "status": "Probably skip",
        "why": "Open this only if foreign income, foreign tax paid, or a manual dividend-credit override still needs review.",
        "note": "If slips already covered the amounts, this section can usually stay closed.",
    },
    "carryforwards": {
        "status": "Probably skip",
        "why": "Open this if you are bringing forward tuition, donation, or province-specific amounts from a prior year.",
        "note": "No carryforward signal is standing out yet.",
    },
}

SCENARIO_DEDUCTION_CANDIDATES = [
    {
        "key": "rrsp_deduction",
        "note_template": "Assumes about {amount} of additional RRSP deduction becomes supportable after a final review.",
        "priority": 1,
    },
    {
        "key": "fhsa_deduction",
        "note_template": "Assumes about {amount} of additional FHSA deduction becomes supportable after a final review.",
        "priority": 2,
    },
    {
        "key": "child_care_expenses",
        "note_template": "Assumes about {amount} of additional child care expenses become supportable after a final review.",
        "priority": 3,
    },
    {
        "key": "moving_expenses",
        "note_template": "Assumes about {amount} of additional moving expenses become supportable after a final review.",
        "priority": 4,
    },
    {
        "key": "support_payments_deduction",
        "note_template": "Assumes about {amount} of additional support deduction becomes supportable after a final review.",
        "priority": 5,
    },
    {
        "key": "carrying_charges",
        "note_template": "Assumes about {amount} of additional carrying charges become supportable after a final review.",
        "priority": 6,
    },
    {
        "key": "other_employment_expenses",
        "note_template": "Assumes about {amount} of additional employment expenses become supportable after a final review.",
        "priority": 7,
    },
    {
        "key": "other_deductions",
        "note_template": "Assumes about {amount} of additional deductions become supportable after a final review.",
        "priority": 8,
    },
]
