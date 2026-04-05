from __future__ import annotations

ELIGIBLE_DIVIDEND_GROSS_UP = 1.38
NON_ELIGIBLE_DIVIDEND_GROSS_UP = 1.15

FEDERAL_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.150198
FEDERAL_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.090301

ONTARIO_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.10
ONTARIO_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.029863
BC_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.12
BC_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.0196
NS_NON_ELIGIBLE_DIVIDEND_CREDIT_RATE = 0.015

FEDERAL_MEDICAL_THRESHOLDS = {
    2025: 2834.0,
}

FEDERAL_AGE_AMOUNTS = {
    2025: {
        "base_amount": 9028.0,
        "income_threshold": 45522.0,
        "phaseout_end": 105709.0,
    },
}

ONTARIO_AGE_AMOUNTS = {
    2025: {
        "base_amount": 6223.0,
        "income_threshold": 46330.0,
        "phaseout_end": 87817.0,
    },
}

ONTARIO_MEDICAL_DEPENDANT_LIMITS = {
    2025: 15551.0,
}

ONTARIO_SPOUSE_AMOUNTS = {
    2025: {
        "base_amount": 11905.0,
        "max_claim": 10823.0,
    },
}

SCHEDULE_9_THRESHOLDS = {
    2025: 253414.0,
}

ONTARIO_LIFT_CONFIG = {
    2025: {
        "employment_rate": 0.0505,
        "max_credit": 875.0,
        "single_threshold": 32500.0,
        "family_threshold": 65000.0,
        "phaseout_rate": 0.05,
    }
}

BC_MEDICAL_THRESHOLDS = {
    2025: 2689.0,
}

BC_DONATION_THRESHOLDS = {
    2025: 259829.0,
}

BC_TAX_REDUCTION_CONFIG = {
    2025: {
        "base_amount": 562.0,
        "net_income_threshold": 25020.0,
        "reduction_rate": 0.0356,
    },
}

NS_AGE_CREDIT_CONFIG = {
    2025: {
        "credit_amount": 1000.0,
        "taxable_income_limit": 24000.0,
    },
}

PE_LOW_INCOME_REDUCTION = {
    2025: {
        "spouse_or_eligible_dependant": 350.0,
        "dependent_child": 300.0,
    },
}

NB_LOW_INCOME_REDUCTION = {
    2025: {
        "spouse_or_eligible_dependant": 802.0,
    },
}

NL_LOW_INCOME_REDUCTION = {
    2025: {
        "spouse_or_eligible_dependant": 557.0,
    },
}

MB_FAMILY_TAX_BENEFIT = {
    2025: {
        "dependent_child_amount": 2752.0,
    },
}

PROVINCIAL_PENSION_AMOUNTS = {
    "AB": {2025: 1719.0},
    "BC": {2025: 1000.0},
    "MB": {2025: 1000.0},
    "NB": {2025: 1000.0},
    "NL": {2025: 1000.0},
    "NS": {2025: 1173.0},
    "ON": {2025: 1762.0},
    "PE": {2025: 1000.0},
    "SK": {2025: 1000.0},
}

CWB_CONFIG = {
    2025: {
        "single": {
            "excluded_working_income": 3000.0,
            "rate": 0.373,
            "max_credit": 1633.0,
            "phaseout_threshold": 26149.0,
            "phaseout_rate": 0.20,
        },
        "family": {
            "excluded_working_income": 3000.0,
            "rate": 0.373,
            "max_credit": 2813.0,
            "phaseout_threshold": 29948.0,
            "phaseout_rate": 0.20,
        },
    },
    2026: {
        "single": {
            "excluded_working_income": 3000.0,
            "rate": 0.373,
            "max_credit": 1680.0,
            "phaseout_threshold": 26850.0,
            "phaseout_rate": 0.20,
        },
        "family": {
            "excluded_working_income": 3000.0,
            "rate": 0.373,
            "max_credit": 2895.0,
            "phaseout_threshold": 30750.0,
            "phaseout_rate": 0.20,
        },
    },
}

CWB_DISABILITY_SUPPLEMENT_CONFIG = {
    2025: {
        "single": {
            "max_credit": 843.0,
            "phaseout_threshold": 37740.0,
            "phaseout_end": 43360.0,
        },
        "family_one_disabled": {
            "max_credit": 843.0,
            "phaseout_threshold": 49389.0,
            "phaseout_end": 55009.0,
        },
        "family_both_disabled": {
            "max_credit": 843.0,
            "phaseout_threshold": 49389.0,
            "phaseout_end": 60629.0,
        },
    },
}

MEDICAL_EXPENSE_SUPPLEMENT_CONFIG = {
    2025: {
        "rate": 0.25,
        "max_credit": 1464.0,
        "employment_income_threshold": 4275.0,
        "phaseout_threshold": 32419.0,
        "phaseout_rate": 0.05,
    },
    2026: {
        "rate": 0.25,
        "max_credit": 1500.0,
        "employment_income_threshold": 4300.0,
        "phaseout_threshold": 33000.0,
        "phaseout_rate": 0.05,
    },
}

ONTARIO_REFUNDABLE_CREDIT_CONFIG = {
    2025: {
        "fertility_rate": 0.25,
        "fertility_expense_cap": 20000.0,
        "seniors_transit_rate": 0.15,
        "seniors_transit_expense_cap": 3000.0,
    }
}

BC_REFUNDABLE_CREDIT_CONFIG = {
    2025: {
        "renter_credit": 400.0,
        "renter_threshold": 64764.0,
        "renter_phaseout_rate": 0.02,
        "renter_zero_threshold": 84764.0,
        "home_reno_rate": 0.10,
        "home_reno_expense_cap": 10000.0,
    }
}
