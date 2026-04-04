import unittest

from tax_engine import calculate_personal_tax_return


def base_input() -> dict:
    return {
        "tax_year": 2025,
        "province": "ON",
        "age": 30,
        "employment_income": 0.0,
        "pension_income": 0.0,
        "rrsp_rrif_income": 0.0,
        "other_income": 0.0,
        "net_rental_income": 0.0,
        "manual_net_rental_income": 0.0,
        "taxable_capital_gains": 0.0,
        "manual_taxable_capital_gains": 0.0,
        "interest_income": 0.0,
        "eligible_dividends": 0.0,
        "non_eligible_dividends": 0.0,
        "t5_eligible_dividends_taxable": 0.0,
        "t5_non_eligible_dividends_taxable": 0.0,
        "t5_federal_dividend_credit": 0.0,
        "t3_eligible_dividends_taxable": 0.0,
        "t3_non_eligible_dividends_taxable": 0.0,
        "t3_federal_dividend_credit": 0.0,
        "spouse_net_income": 0.0,
        "eligible_dependant_net_income": 0.0,
        "additional_dependant_count": 0.0,
        "additional_dependant_caregiver_claim_total": 0.0,
        "additional_dependant_disability_transfer_available_total": 0.0,
        "additional_dependant_medical_claim_total": 0.0,
        "foreign_income": 0.0,
        "foreign_tax_paid": 0.0,
        "t2209_non_business_tax_paid": 0.0,
        "t2209_net_foreign_non_business_income": 0.0,
        "t2209_net_income_override": 0.0,
        "t2209_basic_federal_tax_override": 0.0,
        "t2036_provincial_tax_otherwise_payable_override": 0.0,
        "provincial_dividend_tax_credit_manual": 0.0,
        "ontario_dividend_tax_credit_manual": 0.0,
        "spouse_claim_enabled": False,
        "spouse_infirm": False,
        "eligible_dependant_claim_enabled": False,
        "eligible_dependant_infirm": False,
        "has_spouse_end_of_year": False,
        "rdsp_repayment": 0.0,
        "universal_child_care_benefit": 0.0,
        "rdsp_income": 0.0,
        "spouse_line_21300": 0.0,
        "spouse_rdsp_repayment": 0.0,
        "spouse_uccb": 0.0,
        "spouse_rdsp_income": 0.0,
        "donations_eligible_total": 0.0,
        "schedule9_current_year_donations_available": 0.0,
        "schedule9_current_year_donations_claim_requested": 0.0,
        "schedule9_current_year_donations_claim_used": 0.0,
        "schedule9_current_year_donations_unused": 0.0,
        "schedule9_carryforward_available": 0.0,
        "schedule9_carryforward_claim_requested": 0.0,
        "schedule9_carryforward_claim_used": 0.0,
        "schedule9_carryforward_unused": 0.0,
        "schedule9_total_regular_donations_claimed": 0.0,
        "schedule9_total_regular_donations_unused": 0.0,
        "ecological_cultural_gifts": 0.0,
        "ecological_gifts_pre2016": 0.0,
        "mb479_personal_tax_credit": 0.0,
        "mb479_homeowners_affordability_credit": 0.0,
        "mb479_renters_affordability_credit": 0.0,
        "mb479_seniors_school_rebate": 0.0,
        "mb479_primary_caregiver_credit": 0.0,
        "mb479_fertility_treatment_expenses": 0.0,
        "ns479_volunteer_credit": 0.0,
        "ns479_childrens_sports_arts_credit": 0.0,
        "nb_political_contribution_credit": 0.0,
        "nb_small_business_investor_credit": 0.0,
        "nb_lsvcc_credit": 0.0,
        "nb_seniors_home_renovation_expenses": 0.0,
        "nl_political_contribution_credit": 0.0,
        "nl_direct_equity_credit": 0.0,
        "nl_resort_property_credit": 0.0,
        "nl_venture_capital_credit": 0.0,
        "nl_unused_venture_capital_credit": 0.0,
        "nl479_other_refundable_credits": 0.0,
        "ontario_fertility_treatment_expenses": 0.0,
        "ontario_seniors_public_transit_expenses": 0.0,
        "bc_renters_credit_eligible": False,
        "bc_home_renovation_expenses": 0.0,
        "bc_home_renovation_eligible": False,
        "sk_fertility_treatment_expenses": 0.0,
        "pe_volunteer_credit_eligible": False,
        "canada_workers_benefit": 0.0,
        "cwb_disability_supplement_eligible": False,
        "spouse_cwb_disability_supplement_eligible": False,
        "canada_training_credit_limit_available": 0.0,
        "canada_training_credit": 0.0,
        "medical_expense_supplement": 0.0,
        "other_federal_refundable_credits": 0.0,
        "manual_provincial_refundable_credits": 0.0,
        "other_manual_refundable_credits": 0.0,
        "schedule11_current_year_tuition_available": 0.0,
        "schedule11_carryforward_available": 0.0,
        "schedule11_total_available": 0.0,
        "schedule11_current_year_claim_requested": 0.0,
        "schedule11_current_year_claim_used": 0.0,
        "schedule11_current_year_unused": 0.0,
        "schedule11_carryforward_claim_requested": 0.0,
        "schedule11_carryforward_claim_used": 0.0,
        "schedule11_carryforward_unused": 0.0,
        "schedule11_total_claim_used": 0.0,
        "schedule11_total_unused": 0.0,
        "schedule11_transfer_from_spouse": 0.0,
        "net_capital_loss_carryforward": 0.0,
        "rrsp_deduction": 0.0,
        "fhsa_deduction": 0.0,
        "rpp_contribution": 0.0,
        "union_dues": 0.0,
        "child_care_expenses": 0.0,
        "moving_expenses": 0.0,
        "support_payments_deduction": 0.0,
        "carrying_charges": 0.0,
        "other_employment_expenses": 0.0,
        "other_deductions": 0.0,
        "line_21300": 0.0,
        "other_loss_carryforward": 0.0,
        "income_tax_withheld": 0.0,
        "installments_paid": 0.0,
        "other_payments": 0.0,
        "medical_expenses": 0.0,
        "medical_expenses_dependants": 0.0,
        "disability_amount_claim": 0.0,
        "student_loan_interest": 0.0,
        "ontario_disability_transfer": 0.0,
        "caregiver_amount_claim": 0.0,
        "donations": 0.0,
        "spouse_amount_claim": 0.0,
        "eligible_dependant_amount_claim": 0.0,
        "adoption_expenses": 0.0,
        "tuition_amount_claim": 0.0,
        "provincial_additional_credit_amount": 0.0,
        "dependent_children_count": 0.0,
        "household_medical_expenses_claim": 0.0,
        "another_household_member_claims_caregiver": False,
        "another_household_member_claims_disability_transfer": False,
        "another_person_claims_medical_for_dependant": False,
        "support_payments_to_spouse": False,
        "dependant_relationship": "",
        "dependant_category": "",
        "caregiver_claim_target": "Auto",
        "disability_transfer_source": "Auto",
        "spouse_disability_transfer_available": 0.0,
        "dependant_disability_transfer_available": 0.0,
        "lived_with_you": False,
        "shared_custody_agreement": False,
        "another_household_member_already_claiming": False,
        "child_support_paid": False,
    }


class RegressionCasesTest(unittest.TestCase):
    def assert_close(self, actual: float, expected: float, places: int = 2) -> None:
        self.assertAlmostEqual(actual, expected, places=places)

    def test_ontario_employment_baseline(self) -> None:
        payload = base_input()
        payload.update({"employment_income": 60000.0, "income_tax_withheld": 9000.0})
        result = calculate_personal_tax_return(payload)

        self.assert_close(result["taxable_income"], 59435.00)
        self.assert_close(result["federal_tax"], 5641.47)
        self.assert_close(result["provincial_tax"], 3035.33)
        self.assert_close(result["total_payable"], 8676.79)
        self.assert_close(result["line_48400_refund"], 323.21)

    def test_ontario_foreign_tax_credit_path(self) -> None:
        payload = base_input()
        payload.update(
            {
                "employment_income": 85000.0,
                "foreign_income": 5000.0,
                "foreign_tax_paid": 900.0,
                "t2209_non_business_tax_paid": 900.0,
                "t2209_net_foreign_non_business_income": 5000.0,
            }
        )
        result = calculate_personal_tax_return(payload)

        self.assert_close(result["federal_foreign_tax_credit"], 629.57)
        self.assert_close(result["provincial_foreign_tax_credit"], 270.43)
        self.assert_close(result["total_payable"], 15060.74)
        self.assert_close(result["line_48500_balance_owing"], 15060.74)

    def test_ontario_tuition_and_donation_path(self) -> None:
        payload = base_input()
        payload.update(
            {
                "employment_income": 70000.0,
                "income_tax_withheld": 12000.0,
                "schedule11_current_year_tuition_available": 4000.0,
                "schedule11_current_year_claim_requested": 2500.0,
                "schedule11_carryforward_available": 3000.0,
                "schedule11_carryforward_claim_requested": 1800.0,
                "schedule9_current_year_donations_available": 900.0,
                "schedule9_current_year_donations_claim_requested": 900.0,
                "schedule9_carryforward_available": 1200.0,
                "schedule9_carryforward_claim_requested": 1000.0,
            }
        )
        result = calculate_personal_tax_return(payload)

        self.assert_close(result["schedule11_current_year_claim_used"], 2500.00)
        self.assert_close(result["schedule11_carryforward_claim_used"], 1800.00)
        self.assert_close(result["schedule11_total_claim_used"], 4300.00)
        self.assert_close(result["schedule9_total_regular_donations_claimed"], 1900.00)
        self.assert_close(result["schedule9_carryforward_claim_used"], 1000.00)
        self.assert_close(result["total_payable"], 10351.59)
        self.assert_close(result["line_48400_refund"], 1648.41)

    def test_bc_refundable_credit_path(self) -> None:
        payload = base_input()
        payload.update(
            {
                "province": "BC",
                "employment_income": 42000.0,
                "income_tax_withheld": 3500.0,
                "bc_renters_credit_eligible": True,
                "bc_home_renovation_eligible": True,
                "bc_home_renovation_expenses": 8000.0,
            }
        )
        result = calculate_personal_tax_return(payload)

        self.assert_close(result["bc_renters_credit"], 400.00)
        self.assert_close(result["bc_home_renovation_credit"], 800.00)
        self.assert_close(result["refundable_credits"], 1200.00)
        self.assert_close(result["provincial_tax"], 900.83)
        self.assert_close(result["line_48400_refund"], 693.21)

    def test_ontario_dividend_and_household_path(self) -> None:
        payload = base_input()
        payload.update(
            {
                "employment_income": 95000.0,
                "income_tax_withheld": 17000.0,
                "t5_eligible_dividends_taxable": 3000.0,
                "t5_non_eligible_dividends_taxable": 1200.0,
                "t5_federal_dividend_credit": 450.0,
                "foreign_income": 1800.0,
                "foreign_tax_paid": 240.0,
                "t2209_non_business_tax_paid": 240.0,
                "t2209_net_foreign_non_business_income": 1800.0,
                "spouse_claim_enabled": True,
                "spouse_net_income": 5000.0,
                "spouse_amount_claim": 12000.0,
                "caregiver_amount_claim": 1500.0,
                "dependant_disability_transfer_available": 800.0,
                "disability_transfer_source": "Dependant",
                "ontario_disability_transfer": 700.0,
            }
        )
        result = calculate_personal_tax_return(payload)

        self.assert_close(result["federal_dividend_tax_credit"], 450.00)
        self.assert_close(result["federal_foreign_tax_credit"], 238.99)
        self.assert_close(result["provincial_foreign_tax_credit"], 1.01)
        self.assert_close(result["total_payable"], 19191.73)
        self.assert_close(result["line_48500_balance_owing"], 2191.73)


if __name__ == "__main__":
    unittest.main()
