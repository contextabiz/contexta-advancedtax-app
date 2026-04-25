import streamlit as st

from tax_config import TAX_CONFIGS
from ui_config import PLANNING_PRIORITY_THRESHOLDS


def build_tax_optimization_items(
    result: dict,
    suggestions: list[dict] | None = None,
    *,
    format_currency,
) -> list[tuple[str, str]]:
    suggestions = suggestions or []
    items: list[tuple[int, str, str]] = []

    def add_item(priority: int, title: str, body: str) -> None:
        items.append((priority, title, body))

    spouse_net_income = float(result.get("spouse_net_income_for_lift", 0.0))
    spouse_claim_used = float(result.get("line_30300", 0.0))
    tuition_available = float(result.get("schedule11_total_available", 0.0))
    tuition_claimed = float(result.get("schedule11_total_claim_used", 0.0))
    tuition_unused = max(0.0, tuition_available - tuition_claimed)
    balance_owing = float(result.get("line_48500_balance_owing", 0.0))
    refund_amount = float(result.get("line_48400_refund", 0.0))
    total_deductions = float(result.get("total_deductions", 0.0))
    cwb_amount = float(result.get("canada_workers_benefit", 0.0))
    donation_amount = max(
        float(result.get("schedule9_total_regular_donations_claimed", 0.0)),
        float(result.get("federal_donation_credit", 0.0)),
    )
    foreign_credit_amount = float(result.get("federal_foreign_tax_credit", 0.0)) + float(result.get("provincial_foreign_tax_credit", 0.0))
    spouse_signal = any(str(item.get("id", "")) == "spouse_amount" for item in suggestions)
    tuition_signal = any(str(item.get("id", "")) == "tuition_and_student" for item in suggestions)
    deduction_signal = any(str(item.get("id", "")) == "deductions_review" for item in suggestions)
    medical_donation_signal = any(str(item.get("id", "")) == "medical_and_donations" for item in suggestions)
    foreign_signal = any(str(item.get("id", "")) == "foreign_and_investment" for item in suggestions)
    low_income_signal = any(str(item.get("id", "")) == "low_income_refundable" for item in suggestions)

    if spouse_signal and spouse_claim_used <= 0.0 and spouse_net_income > 0.0 and spouse_net_income < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]:
        add_item(
            10,
            "Possible spouse amount review",
            "On the facts entered so far, spouse amount may still be supportable if your spouse or partner had low net income at year end and that position has not yet been fully worked through.",
        )
    if tuition_signal and tuition_unused >= PLANNING_PRIORITY_THRESHOLDS["material_tuition_room"]:
        add_item(
            20,
            "Unused tuition room still showing",
            f"The file is still showing about {format_currency(tuition_unused)} of tuition room unused, so a Schedule 11 or carryforward review may still improve the current filing position.",
        )
    if deduction_signal and balance_owing >= PLANNING_PRIORITY_THRESHOLDS["high_balance_owing"] and total_deductions < PLANNING_PRIORITY_THRESHOLDS["light_deduction_usage"]:
        add_item(
            30,
            "Deduction review may still reduce the balance owing",
            "The balance owing remains material relative to the deductions entered, so RRSP, FHSA, child care, moving, support, or work-related deductions may still be worth reviewing before filing.",
        )
    if low_income_signal and cwb_amount <= 0.0:
        add_item(
            40,
            "Refundable support may still be worth checking",
            "Based on the current income picture, Canada Workers Benefit, the disability supplement path, or the Medical Expense Supplement may still be relevant on this file.",
        )
    if medical_donation_signal and donation_amount <= 0.0:
        add_item(
            50,
            "Medical or donation credits may still be underused",
            "Medical expenses or charitable donations may still create non-refundable credits if those amounts have not yet been fully worked through.",
        )
    if foreign_signal and foreign_credit_amount <= 0.0 and refund_amount <= 0.0:
        add_item(
            60,
            "Foreign tax inputs may still need positioning",
            "If foreign income or tax paid was entered elsewhere but not fully matched here, the foreign credit position may still change the return outcome.",
        )

    items.sort(key=lambda row: row[0])
    return [(title, body) for _, title, body in items[:3]]


def build_advisor_summary_lead(result: dict, *, format_currency, include_outcome: bool = True) -> str:
    refund_amount = float(result.get("line_48400_refund", 0.0))
    balance_owing_amount = float(result.get("line_48500_balance_owing", 0.0))
    deductions = float(result.get("total_deductions", 0.0))
    refundable_credits = float(result.get("refundable_credits", 0.0))
    withholding = float(result.get("income_tax_withheld", 0.0))

    if refund_amount > 0:
        outcome = f"Estimated refund: {format_currency(refund_amount)}."
    elif balance_owing_amount > 0:
        outcome = f"Estimated balance owing: {format_currency(balance_owing_amount)}."
    else:
        outcome = "Estimated result: close to break-even."

    drivers: list[str] = []
    if withholding > 0:
        drivers.append("withholding already entered")
    if deductions > 0:
        drivers.append("deductions currently claimed")
    if refundable_credits > 0:
        drivers.append("refundable credits in the estimate")

    if drivers:
        driver_text = ", ".join(drivers[:-1]) + (f", and {drivers[-1]}" if len(drivers) > 1 else drivers[0])
        body = (
            f"The current position appears to be driven mainly by {driver_text}. "
            "The notes below highlight where the file may still move or need support."
        )
    else:
        body = (
            "The next check is whether all available deductions, credits, and household positions "
            "have actually been worked through."
        )

    return f"{outcome} {body}" if include_outcome else body


def build_intake_summary_context(calculation_inputs: dict | None) -> dict[str, object]:
    inputs = calculation_inputs or {}
    spouse_household_signal = bool(inputs.get("screen_step5_household", False))
    tuition_signal = bool(inputs.get("screen_step5_common_credits", False)) and (
        float(inputs.get("student_loan_interest", 0.0)) > 0.0
        or bool(inputs.get("screen_step5_carryforwards", False))
        or float(inputs.get("tuition_amount_claim", 0.0)) > 0.0
        or bool(inputs.get("tuition_carryforwards"))
    )
    deduction_signal = any(
        bool(inputs.get(key, False))
        for key in [
            "screen_step4_rrsp_fhsa",
            "screen_step4_family_work_move",
            "screen_step4_work_from_home",
            "screen_step4_employment_investment",
        ]
    )
    work_from_home_signal = bool(inputs.get("screen_step4_work_from_home", False))
    foreign_provincial_signal = bool(inputs.get("screen_step5_foreign_province_manual", False))
    refundable_signal = bool(inputs.get("screen_step5_refundable", False))
    payment_cleanup_signal = any(
        bool(inputs.get(key, False))
        for key in [
            "screen_step6_installments",
            "screen_step6_other_payments",
            "screen_step6_manual_withholding",
        ]
    )

    review_areas: list[str] = []
    if spouse_household_signal:
        review_areas.append("household positions")
    if deduction_signal:
        review_areas.append("deduction review")
    if tuition_signal:
        review_areas.append("tuition or carryforward review")
    if foreign_provincial_signal:
        review_areas.append("foreign or province-specific worksheets")
    if payment_cleanup_signal:
        review_areas.append("payment and withholding cleanup")

    return {
        "spouse_household_signal": spouse_household_signal,
        "tuition_signal": tuition_signal,
        "deduction_signal": deduction_signal,
        "work_from_home_signal": work_from_home_signal,
        "foreign_provincial_signal": foreign_provincial_signal,
        "refundable_signal": refundable_signal,
        "payment_cleanup_signal": payment_cleanup_signal,
        "review_areas": review_areas,
    }


def join_with_and(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def build_return_memo_html(result: dict, calculation_inputs: dict | None = None, *, format_currency) -> str:
    memo_text = build_advisor_summary_lead(result, format_currency=format_currency, include_outcome=True)
    intake_context = build_intake_summary_context(calculation_inputs)
    review_areas = list(intake_context["review_areas"])
    if review_areas:
        memo_text = (
            f"{memo_text} Based on the intake so far, the file still points most clearly to "
            f"{join_with_and(review_areas)} before the estimate is treated as final."
        )
    elif bool(intake_context["refundable_signal"]):
        memo_text = (
            f"{memo_text} The intake also suggests refundable-support review may still matter before filing."
        )
    highlight_style = (
        "display:inline-block;padding:1px 8px 2px 8px;border-radius:999px;"
        "background:rgba(94, 166, 255, 0.14);border:1px solid rgba(94, 166, 255, 0.22);"
        "color:#F2F7FF;font-weight:700;letter-spacing:0.01em;"
    )

    if result.get("line_48400_refund", 0.0) > 0:
        amount_text = format_currency(result["line_48400_refund"])
        memo_text = memo_text.replace(amount_text, f"<span style='{highlight_style}'>{amount_text}</span>", 1)
    elif result.get("line_48500_balance_owing", 0.0) > 0:
        amount_text = format_currency(result["line_48500_balance_owing"])
        memo_text = memo_text.replace(amount_text, f"<span style='{highlight_style}'>{amount_text}</span>", 1)

    return memo_text


def format_result_outcome_chip(result: dict, *, format_currency) -> str:
    refund_amount = float(result.get("line_48400_refund", 0.0))
    balance_owing_amount = float(result.get("line_48500_balance_owing", 0.0))
    if refund_amount > 0:
        return f"Refund {format_currency(refund_amount)}"
    if balance_owing_amount > 0:
        return f"Balance owing {format_currency(balance_owing_amount)}"
    return "Near break-even"


def scenario_improvement_value(current_result: dict, scenario_result: dict) -> float:
    current_refund = float(current_result.get("line_48400_refund", 0.0))
    current_balance = float(current_result.get("line_48500_balance_owing", 0.0))
    scenario_refund = float(scenario_result.get("line_48400_refund", 0.0))
    scenario_balance = float(scenario_result.get("line_48500_balance_owing", 0.0))
    return (scenario_refund - current_refund) + (current_balance - scenario_balance)


def format_scenario_delta(current_result: dict, scenario_result: dict, *, format_currency) -> str:
    delta = scenario_improvement_value(current_result, scenario_result)
    if abs(delta) < 0.005:
        return "No meaningful change"
    if delta > 0:
        if float(current_result.get("line_48500_balance_owing", 0.0)) > 0 or float(scenario_result.get("line_48500_balance_owing", 0.0)) > 0:
            return f"Improves by about {format_currency(delta)}"
        return f"Increases refund by about {format_currency(delta)}"
    if float(current_result.get("line_48400_refund", 0.0)) > 0:
        return f"Reduces refund by about {format_currency(abs(delta))}"
    return f"Worsens by about {format_currency(abs(delta))}"


def get_current_bracket_index(taxable_income: float, brackets: list[tuple[float, float]]) -> int:
    for index, (limit, _) in enumerate(brackets):
        if taxable_income <= float(limit):
            return index
    return max(0, len(brackets) - 1)


def build_bracket_drop_target(
    *,
    taxable_income: float,
    tax_year: int,
    province: str,
) -> dict[str, float | str] | None:
    config = TAX_CONFIGS.get(tax_year)
    province_code = str(province or "").upper()
    if not config or province_code not in config.get("provincial", {}):
        return None
    if taxable_income <= 0:
        return None

    federal_brackets = list(config["federal_brackets"])
    provincial_config = config["provincial"][province_code]
    provincial_brackets = list(provincial_config["brackets"])
    candidates: list[dict[str, float | str]] = []

    federal_index = get_current_bracket_index(taxable_income, federal_brackets)
    if federal_index > 0:
        previous_limit = float(federal_brackets[federal_index - 1][0])
        candidates.append(
            {
                "scope": "federal",
                "label": "federal bracket",
                "amount_needed": max(0.0, taxable_income - previous_limit),
            }
        )

    provincial_index = get_current_bracket_index(taxable_income, provincial_brackets)
    if provincial_index > 0:
        previous_limit = float(provincial_brackets[provincial_index - 1][0])
        candidates.append(
            {
                "scope": "provincial",
                "label": f"{provincial_config['name']} bracket",
                "amount_needed": max(0.0, taxable_income - previous_limit),
            }
        )

    if not candidates:
        return None
    return sorted(candidates, key=lambda item: float(item["amount_needed"]))[0]


def choose_bracket_drop_deduction_key(calculation_inputs: dict) -> tuple[str, str]:
    rrsp_deduction = float(calculation_inputs.get("rrsp_deduction", 0.0))
    fhsa_deduction = float(calculation_inputs.get("fhsa_deduction", 0.0))
    if fhsa_deduction > rrsp_deduction:
        return "fhsa_deduction", "FHSA"
    return "rrsp_deduction", "RRSP"


def build_advisor_summary_scenarios(
    current_result: dict,
    calculation_inputs: dict | None,
    *,
    calculate_personal_tax_return,
    format_currency,
) -> list[dict[str, str]]:
    intake_context = build_intake_summary_context(calculation_inputs)
    cards: list[dict[str, str]] = [
        {
            "title": "Current Return",
            "outcome": format_result_outcome_chip(current_result, format_currency=format_currency),
            "delta": "Current filed position",
            "note": (
                "Based on the inputs currently entered."
                if not intake_context["review_areas"]
                else f"Current filed position before {join_with_and(list(intake_context['review_areas']))} is fully worked through."
            ),
        }
    ]
    if not calculation_inputs:
        return cards + [
            {
                "title": "With spouse amount",
                "outcome": "No clear additional benefit",
                "delta": "No clear additional benefit on current facts",
                "note": "Add spouse facts first if you want to compare this scenario.",
            },
            {
                "title": "With tuition review",
                "outcome": "No clear additional benefit",
                "delta": "No clear additional benefit on current facts",
                "note": "Add tuition, carryforward, or student-loan inputs first if you want to compare this scenario.",
            },
            {
                "title": "With deduction cleanup",
                "outcome": "No clear additional benefit",
                "delta": "No clear additional benefit on current facts",
                "note": "Add deduction signals first if you want to compare this scenario.",
            },
        ]

    scenario_map: dict[str, dict[str, str]] = {}

    def set_default_scenario(title: str, note: str) -> None:
        scenario_map[title] = {
            "title": title,
            "outcome": "No clear additional benefit",
            "delta": "No clear additional benefit on current facts",
            "note": note,
        }

    def try_add_scenario(title: str, note: str, updates: dict[str, float | bool]) -> None:
        scenario_inputs = dict(calculation_inputs)
        scenario_inputs.update(updates)
        scenario_result = calculate_personal_tax_return(scenario_inputs)
        scenario_map[title] = {
            "title": title,
            "outcome": format_result_outcome_chip(scenario_result, format_currency=format_currency),
            "delta": format_scenario_delta(current_result, scenario_result, format_currency=format_currency),
            "note": note,
        }

    spouse_net_income = float(calculation_inputs.get("spouse_net_income", 0.0))
    set_default_scenario(
        "With spouse amount",
        (
            "The intake is not currently pointing to a spouse support review strong enough to move this file."
            if intake_context["spouse_household_signal"]
            else "No spouse review opportunity is standing out yet from the current facts entered."
        ),
    )
    if (
        bool(calculation_inputs.get("has_spouse_end_of_year", False))
        and (
            float(current_result.get("line_30300", 0.0)) <= 0.0
            or spouse_net_income < PLANNING_PRIORITY_THRESHOLDS["spouse_low_income_upper"]
        )
    ):
        try_add_scenario(
            "With spouse amount",
            (
                "You indicated spouse or household review facts during intake. This scenario assumes the spouse amount position is fully worked through using the spouse facts already entered."
            ),
            {
                "spouse_claim_enabled": True,
                "spouse_amount_claim": 0.0,
            },
        )

    current_year_tuition_available = float(current_result.get("schedule11_current_year_tuition_available", 0.0))
    tuition_carryforward_available = float(current_result.get("schedule11_carryforward_available", 0.0))
    set_default_scenario(
        "With tuition review",
        (
            "The intake does not yet show a strong tuition, carryforward, or student-loan review opportunity."
            if intake_context["tuition_signal"]
            else "No material tuition, carryforward, or student-loan review signal is standing out yet."
        ),
    )
    if (
        current_year_tuition_available > 0.0
        or tuition_carryforward_available > 0.0
        or float(calculation_inputs.get("student_loan_interest", 0.0)) > 0.0
    ):
        try_add_scenario(
            "With tuition review",
            (
                "You indicated tuition or carryforward review facts during intake. This scenario assumes available tuition, student-loan, and carryforward amounts are fully reviewed and positioned."
            ),
            {
                "tuition_amount_claim": current_year_tuition_available,
                "schedule11_current_year_claim_requested": current_year_tuition_available,
                "schedule11_carryforward_claim_requested": tuition_carryforward_available,
            },
        )

    balance_owing = float(current_result.get("line_48500_balance_owing", 0.0))
    taxable_income = float(current_result.get("taxable_income", 0.0))
    tax_year = int(calculation_inputs.get("tax_year", 2025) or 2025)
    province = str(calculation_inputs.get("province", "ON") or "ON")
    set_default_scenario(
        "With deduction cleanup",
        (
            "The intake is not yet showing a deduction review strong enough to support a bracket-step scenario."
            if intake_context["deduction_signal"]
            else "No RRSP or FHSA bracket-step opportunity is standing out yet from the current inputs."
        ),
    )
    bracket_drop_target = build_bracket_drop_target(
        taxable_income=taxable_income,
        tax_year=tax_year,
        province=province,
    )
    if balance_owing > 0.0 and bracket_drop_target is not None and float(bracket_drop_target["amount_needed"]) > 0.0:
        deduction_key, deduction_label = choose_bracket_drop_deduction_key(calculation_inputs)
        contribution_needed = float(bracket_drop_target["amount_needed"])
        try_add_scenario(
            "With deduction cleanup",
            (
                f"You indicated deduction-review facts during intake. This scenario assumes about {format_currency(contribution_needed)} "
                f"of additional {deduction_label} contribution, claimed as a deduction, to bring taxable income down into the next lower "
                f"{bracket_drop_target['label']}."
            ),
            {
                deduction_key: float(calculation_inputs.get(deduction_key, 0.0)) + contribution_needed,
            },
        )
    elif intake_context["work_from_home_signal"]:
        scenario_map["With deduction cleanup"]["note"] = (
            "The intake points more toward employment or workspace deduction review than a clear RRSP/FHSA bracket-step move on the current facts."
        )

    cards.extend(
        [
            scenario_map["With deduction cleanup"],
            scenario_map["With spouse amount"],
            scenario_map["With tuition review"],
        ]
    )
    return cards[:4]


def render_advisor_scenario_compare(
    current_result: dict,
    calculation_inputs: dict | None,
    *,
    calculate_personal_tax_return,
    format_currency,
) -> None:
    scenario_cards = build_advisor_summary_scenarios(
        current_result,
        calculation_inputs,
        calculate_personal_tax_return=calculate_personal_tax_return,
        format_currency=format_currency,
    )
    with st.container():
        st.markdown("<div style='height:1px;background:rgba(255,255,255,0.08);margin:10px 0 16px 0;'></div>", unsafe_allow_html=True)
        st.markdown("##### Scenario Compare")
        st.caption("RRSP/FHSA scenario is subject to available contribution room and supportable deduction limits.")
        columns = st.columns(len(scenario_cards))
        for column, card in zip(columns, scenario_cards):
            with column:
                st.markdown(
                    (
                        "<div style='background:#101826;border:1px solid rgba(255,255,255,0.08);"
                        "border-radius:16px;padding:14px 15px 15px 15px;min-height:178px;margin:0 0 14px 0;'>"
                        f"<div style='font-size:0.78rem;letter-spacing:0.06em;text-transform:uppercase;color:#8FA8C6;font-weight:700;margin-bottom:8px;'>{card['title']}</div>"
                        f"<div style='color:#F2F7FF;font-weight:700;font-size:1.02rem;line-height:1.4;margin-bottom:8px;'>{card['outcome']}</div>"
                        f"<div style='display:inline-block;padding:4px 10px;border-radius:999px;background:rgba(94, 166, 255, 0.12);"
                        f"color:#D8E9FF;border:1px solid rgba(94, 166, 255, 0.18);font-size:0.78rem;font-weight:700;margin-bottom:10px;'>{card['delta']}</div>"
                        f"<div style='color:#B9C7D8;line-height:1.55;font-size:0.90rem;'>{card['note']}</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
