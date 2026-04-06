from typing import Literal, TypedDict


class EligibilityContext(TypedDict):
    tax_year: int
    province: str
    age: float
    has_spouse: bool
    spouse_net_income: float
    spouse_infirm: bool
    has_spouse_end_of_year: bool
    separated_in_year: bool
    support_payments_to_spouse: bool
    eligible_dependant_claim_enabled: bool
    eligible_dependant_net_income: float
    eligible_dependant_infirm: bool
    dependant_lived_with_you: bool
    dependant_relationship: str
    dependant_category: str
    paid_child_support_for_dependant: bool
    shared_custody_claim_agreement: bool
    another_household_member_claims_dependant: bool
    another_household_member_claims_caregiver: bool
    another_household_member_claims_disability_transfer: bool
    medical_dependant_claim_shared: bool
    caregiver_claim_amount: float
    caregiver_claim_target: str
    ontario_disability_transfer: float
    disability_transfer_source: str
    spouse_disability_transfer_available: bool
    spouse_disability_transfer_available_amount: float
    dependant_disability_transfer_available: bool
    dependant_disability_transfer_available_amount: float
    ontario_medical_dependants: float
    cwb_basic_eligible: bool
    cwb_disability_supplement_eligible: bool
    spouse_cwb_disability_supplement_eligible: bool
    working_income: float
    adjusted_net_income: float
    spouse_adjusted_net_income: float
    cwb_preview_amount: float
    cwb_no_basic_amount_above: float
    tuition_amount_available: float
    tuition_transfer_from_spouse: float
    tuition_carryforward_available: float
    canada_training_credit_limit_available: float


class EligibilityRuleResult(TypedDict):
    id: str
    category: str
    status: Literal["allowed", "blocked", "review"]
    message: str
    where: str
    affects: list[str]


class EligibilityDecision(TypedDict):
    rule_results: list[EligibilityRuleResult]
    allowed_claims: dict[str, bool]
    blocked_claims: dict[str, bool]
    review_flags: list[str]
