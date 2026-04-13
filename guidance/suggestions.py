from typing import Literal, TypedDict

from .completion import CompletionFlag
from .guidance_builder import GuidanceItem
from .progress import SectionProgress
from .screening import ScreeningInputs


class SuggestionItem(TypedDict):
    id: str
    label: str
    reason: str
    where: str
    priority: Literal["important", "review", "info", "maybe"]


def build_suggestions(
    *,
    screening: ScreeningInputs,
    guidance_items: list[GuidanceItem],
    progress: SectionProgress | None = None,
    completion_flags: list[CompletionFlag] | None = None,
) -> list[SuggestionItem]:
    suggestions: list[SuggestionItem] = []
    seen_keys: set[tuple[str, str, str]] = set()
    covered_guidance_ids: set[str] = set()

    def add_suggestion(
        suggestion_id: str,
        label: str,
        reason: str,
        where: str,
        priority: Literal["important", "review", "info", "maybe"],
    ) -> None:
        key = (label, reason, where)
        if key in seen_keys:
            return
        seen_keys.add(key)
        suggestions.append(
            {
                "id": suggestion_id,
                "label": label,
                "reason": reason,
                "where": where,
                "priority": priority,
            }
        )

    if progress is not None and progress["section_1_slips"] == "not_started":
        add_suggestion(
            "start_with_slips",
            "Start with your slips.",
            "Most returns should begin with T-slips before deductions or credits.",
            "Step 1 -> Slips",
            "important",
        )

    severity_to_priority = {
        "important": "important",
        "review": "review",
        "info": "info",
    }
    for flag in completion_flags or []:
        add_suggestion(
            flag["id"],
            "Review this area" if flag["severity"] in {"important", "review"} else "Check this item",
            flag["message"],
            flag["where"],
            severity_to_priority[flag["severity"]],
        )
        if flag["related_guidance_id"]:
            covered_guidance_ids.add(flag["related_guidance_id"])

    guidance_to_priority = {
        "likely": "review",
        "maybe": "maybe",
        "easy_to_miss": "info",
    }
    for item in guidance_items:
        if item["id"] in covered_guidance_ids:
            continue
        add_suggestion(
            item["id"],
            item["what"],
            item["why"],
            item["where"],
            guidance_to_priority[item["priority"]],
        )

    if suggestions:
        return suggestions

    if screening["had_work_expenses"] or screening["had_moving_expenses"] or screening["had_child_care_expenses"]:
        add_suggestion(
            "review_deductions",
            "Review deductions.",
            "Deductions are one of the most common places where first-time users miss tax savings.",
            "Step 4 -> Deductions",
            "review",
        )
    if screening["had_medical_expenses"] or screening["made_donations"]:
        add_suggestion(
            "review_common_credits",
            "Review common credits.",
            "Medical expenses and donations are common items that change the final result.",
            "Step 5 -> Common Credits And Claim Amounts",
            "maybe",
        )
    if screening["had_foreign_income"] or screening["had_investment_income"]:
        add_suggestion(
            "review_income_and_foreign_tax",
            "Review income and foreign-tax details.",
            "Investment and foreign-income entries are more error-prone and often worth a second look.",
            "Step 3 -> Income And Investment and Step 5 -> Foreign Tax And Dividend Credits",
            "maybe",
        )
    return suggestions
