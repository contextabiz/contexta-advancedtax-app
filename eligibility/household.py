from .types import EligibilityContext, EligibilityRuleResult


def evaluate_household_eligibility(ctx: EligibilityContext) -> list[EligibilityRuleResult]:
    results: list[EligibilityRuleResult] = []

    if ctx["has_spouse"] and not ctx["has_spouse_end_of_year"]:
        results.append({
            "id": "spouse_requires_year_end_status",
            "category": "household",
            "status": "review",
            "message": "A spouse or partner is indicated, but year-end spouse status is not confirmed.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["spouse_amount"],
        })
    if ctx["has_spouse_end_of_year"] and ctx["support_payments_to_spouse"]:
        results.append({
            "id": "spouse_support_restriction",
            "category": "household",
            "status": "blocked",
            "message": "Support payments to a spouse or partner may block or change the spouse amount claim.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["spouse_amount"],
        })
    if ctx["has_spouse_end_of_year"] and not ctx["separated_in_year"] and not ctx["support_payments_to_spouse"]:
        results.append({
            "id": "spouse_household_path_reviewed",
            "category": "household",
            "status": "allowed",
            "message": "Spouse amount settings look broadly consistent for a basic review path.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["spouse_amount"],
        })
    if ctx["eligible_dependant_claim_enabled"] and ctx["another_household_member_claims_dependant"]:
        results.append({
            "id": "eligible_dependant_other_claimant",
            "category": "household",
            "status": "blocked",
            "message": "Another household member is marked as claiming the dependant.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["eligible_dependant"],
        })
    if ctx["eligible_dependant_claim_enabled"] and ctx["paid_child_support_for_dependant"] and not ctx["shared_custody_claim_agreement"]:
        results.append({
            "id": "eligible_dependant_support_review",
            "category": "household",
            "status": "review",
            "message": "Child support is indicated for the dependant, so eligible dependant rules need a closer review.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["eligible_dependant"],
        })
    if ctx["another_household_member_claims_caregiver"] and ctx["caregiver_claim_amount"] > 0:
        results.append({
            "id": "caregiver_other_claimant",
            "category": "household",
            "status": "blocked",
            "message": "A caregiver amount is entered, but another household member is already marked as claiming the caregiver amount.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["caregiver_amount"],
        })
    if (
        ctx["caregiver_claim_amount"] > 0
        and ctx["caregiver_claim_target"] == "Auto"
        and ctx["spouse_infirm"]
        and ctx["eligible_dependant_infirm"]
    ):
        results.append({
            "id": "caregiver_target_ambiguous",
            "category": "household",
            "status": "review",
            "message": "Caregiver amount is entered while both spouse and dependant are infirm. Pick a caregiver target to avoid ambiguity.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["caregiver_amount"],
        })
    if (
        ctx["caregiver_claim_amount"] > 0
        and ctx["eligible_dependant_infirm"]
        and ctx["dependant_category"] not in {"Adult child", "Parent/Grandparent", "Other adult relative"}
    ):
        results.append({
            "id": "caregiver_dependant_category_review",
            "category": "household",
            "status": "review",
            "message": "A caregiver amount is entered for an infirm dependant, but the dependant category does not indicate an adult dependant.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["caregiver_amount"],
        })
    if (
        ctx["caregiver_claim_amount"] > 0
        and not (ctx["spouse_infirm"] or ctx["eligible_dependant_infirm"] or ctx["dependant_lived_with_you"])
    ):
        results.append({
            "id": "caregiver_supporting_context_missing",
            "category": "household",
            "status": "review",
            "message": "A caregiver amount is entered, but no infirm spouse/dependant or dependant living arrangement is indicated.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["caregiver_amount"],
        })
    if ctx["another_household_member_claims_disability_transfer"] and ctx["ontario_disability_transfer"] > 0:
        results.append({
            "id": "disability_transfer_other_claimant",
            "category": "household",
            "status": "blocked",
            "message": "A disability transfer is entered, but another household member is already marked as claiming the disability transfer.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if (
        ctx["ontario_disability_transfer"] > 0
        and ctx["disability_transfer_source"] == "Auto"
        and ctx["spouse_infirm"]
        and ctx["eligible_dependant_infirm"]
    ):
        results.append({
            "id": "disability_transfer_source_ambiguous",
            "category": "household",
            "status": "review",
            "message": "Disability transfer is entered while both spouse and dependant could qualify. Pick a transfer source to avoid ambiguity.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if ctx["ontario_disability_transfer"] > 0 and ctx["spouse_infirm"] and not ctx["spouse_disability_transfer_available"]:
        results.append({
            "id": "spouse_disability_transfer_unavailable",
            "category": "household",
            "status": "blocked",
            "message": "A spouse disability transfer is entered, but spouse disability transfer availability is not indicated.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if (
        ctx["ontario_disability_transfer"] > 0
        and ctx["spouse_infirm"]
        and ctx["spouse_disability_transfer_available_amount"] > 0
        and ctx["ontario_disability_transfer"] > ctx["spouse_disability_transfer_available_amount"]
    ):
        results.append({
            "id": "spouse_disability_transfer_exceeds_available",
            "category": "household",
            "status": "review",
            "message": "The spouse disability transfer entered is higher than the available spouse transfer amount.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if ctx["ontario_disability_transfer"] > 0 and ctx["eligible_dependant_infirm"] and not ctx["dependant_disability_transfer_available"]:
        results.append({
            "id": "dependant_disability_transfer_unavailable",
            "category": "household",
            "status": "blocked",
            "message": "A dependant disability transfer is entered, but dependant disability transfer availability is not indicated.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if (
        ctx["ontario_disability_transfer"] > 0
        and ctx["eligible_dependant_infirm"]
        and ctx["dependant_disability_transfer_available_amount"] > 0
        and ctx["ontario_disability_transfer"] > ctx["dependant_disability_transfer_available_amount"]
    ):
        results.append({
            "id": "dependant_disability_transfer_exceeds_available",
            "category": "household",
            "status": "review",
            "message": "The dependant disability transfer entered is higher than the available dependant transfer amount.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if (
        ctx["ontario_disability_transfer"] > 0
        and not (ctx["spouse_infirm"] or ctx["eligible_dependant_infirm"])
    ):
        results.append({
            "id": "disability_transfer_no_source_context",
            "category": "household",
            "status": "review",
            "message": "A disability transfer is entered, but no qualifying spouse or dependant disability context is indicated.",
            "where": "Step 5 -> Household And Dependants",
            "affects": ["disability_transfer"],
        })
    if ctx["medical_dependant_claim_shared"] and ctx["ontario_medical_dependants"] > 0:
        results.append({
            "id": "medical_dependants_shared_review",
            "category": "household",
            "status": "review",
            "message": "Medical expenses for dependants are marked as shared, so double-check who is claiming the amount.",
            "where": "Section 4 -> Household And Dependants",
            "affects": ["medical_dependants"],
        })
    if ctx["ontario_medical_dependants"] > 0 and ctx["dependant_category"] in {"Child under 18", "Minor child"}:
        results.append({
            "id": "medical_dependants_minor_child_review",
            "category": "household",
            "status": "review",
            "message": "Medical expenses for dependants are entered for a minor child. Review the most appropriate claimant and threshold treatment.",
            "where": "Section 4 -> Household And Dependants",
            "affects": ["medical_dependants"],
        })

    return results
