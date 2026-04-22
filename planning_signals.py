from ui_config import PLANNING_PRIORITY_THRESHOLDS


def build_planning_priority_context(
    result: dict,
    inside_items: list[dict],
    refund_amount: float,
    balance_owing_amount: float,
) -> dict[str, float | bool | set[str]]:
    inside_ids = {str(item.get("id", "")) for item in inside_items}
    spouse_claim_used = float(result.get("line_30300", 0.0))
    spouse_net_income_for_review = float(result.get("spouse_net_income_for_lift", 0.0))
    tuition_available_total = float(result.get("schedule11_total_available", 0.0))
    tuition_claim_used_total = float(result.get("schedule11_total_claim_used", 0.0))
    total_deductions_used = float(result.get("total_deductions", 0.0))
    tuition_unused_total = max(0.0, tuition_available_total - tuition_claim_used_total)

    has_spouse_signal = "spouse_amount" in inside_ids or spouse_claim_used > 0
    has_household_signal = (
        "household_dependants" in inside_ids
        or result.get("line_30400", 0.0) > 0
        or result.get("caregiver_amount_claim", 0.0) > 0
    )
    has_tuition_signal = "tuition_and_student" in inside_ids or tuition_claim_used_total > 0
    has_low_income_signal = (
        "low_income_refundable" in inside_ids
        or result.get("canada_workers_benefit", 0.0) > 0
        or result.get("medical_expense_supplement", 0.0) > 0
    )
    has_deduction_signal = "deductions_review" in inside_ids or total_deductions_used > 0
    has_medical_donation_signal = (
        "medical_and_donations" in inside_ids
        or result.get("schedule9_total_regular_donations_claimed", 0.0) > 0
        or result.get("federal_donation_credit", 0.0) > 0
    )
    has_foreign_signal = (
        "foreign_and_investment" in inside_ids
        or result.get("federal_foreign_tax_credit", 0.0) + result.get("provincial_foreign_tax_credit", 0.0) > 0
    )

    return {
        "inside_ids": inside_ids,
        "refund_amount": refund_amount,
        "balance_owing_amount": balance_owing_amount,
        "has_spouse_signal": has_spouse_signal,
        "has_household_signal": has_household_signal,
        "has_tuition_signal": has_tuition_signal,
        "has_low_income_signal": has_low_income_signal,
        "has_deduction_signal": has_deduction_signal,
        "has_medical_donation_signal": has_medical_donation_signal,
        "has_foreign_signal": has_foreign_signal,
        "spouse_claim_used": spouse_claim_used,
        "spouse_net_income_for_review": spouse_net_income_for_review,
        "tuition_available_total": tuition_available_total,
        "tuition_claim_used_total": tuition_claim_used_total,
        "tuition_unused_total": tuition_unused_total,
        "total_deductions_used": total_deductions_used,
        "high_balance_owing": balance_owing_amount >= PLANNING_PRIORITY_THRESHOLDS["high_balance_owing"],
        "spouse_amount_not_used_but_may_be_available": (
            has_spouse_signal
            and spouse_claim_used <= 0.0
            and spouse_net_income_for_review > 0.0
            and spouse_net_income_for_review < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]
        ),
        "material_tuition_room_remaining": (
            has_tuition_signal and tuition_unused_total >= PLANNING_PRIORITY_THRESHOLDS["material_tuition_room"]
        ),
    }


def planning_priority(
    base: int,
    context: dict[str, float | bool | set[str]],
    *,
    spouse: bool = False,
    household: bool = False,
    tuition: bool = False,
    low_income: bool = False,
    deduction: bool = False,
    medical_donation: bool = False,
    foreign: bool = False,
) -> int:
    priority = base
    balance_owing_amount = float(context["balance_owing_amount"])
    refund_amount = float(context["refund_amount"])
    high_balance_owing = bool(context["high_balance_owing"])

    if balance_owing_amount > 0:
        if deduction:
            priority -= 8
        if spouse or household or tuition or medical_donation or low_income:
            priority -= 5
    if high_balance_owing:
        if deduction:
            priority -= 10
        if spouse or household or tuition or medical_donation:
            priority -= 6
    if refund_amount > 0:
        if spouse or household or tuition:
            priority -= 3
        if foreign:
            priority += 4
    if spouse and bool(context["has_spouse_signal"]):
        priority -= 10
    if spouse and bool(context["spouse_amount_not_used_but_may_be_available"]):
        priority -= 12
    if household and bool(context["has_household_signal"]):
        priority -= 6
    if tuition and bool(context["has_tuition_signal"]):
        priority -= 8
    if tuition and bool(context["material_tuition_room_remaining"]):
        priority -= 12
    if low_income and bool(context["has_low_income_signal"]):
        priority -= 7
    if deduction and bool(context["has_deduction_signal"]):
        priority -= 6
    if deduction and high_balance_owing and float(context["total_deductions_used"]) < PLANNING_PRIORITY_THRESHOLDS["light_deduction_usage"]:
        priority -= 6
    if medical_donation and bool(context["has_medical_donation_signal"]):
        priority -= 4
    if foreign and bool(context["has_foreign_signal"]):
        priority -= 2
    return priority
