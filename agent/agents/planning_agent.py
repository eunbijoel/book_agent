from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.prompts.planning_prompts import PLANNING_SYSTEM, PLANNING_USER
from agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def _strip_markdown_fences(raw: str) -> str:
    """Remove ```json ... ``` wrappers that some models add."""
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl > 0:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _repair_truncated_json(raw: str) -> dict | None:
    """Try to repair JSON that was truncated mid-generation."""
    raw = _strip_markdown_fences(raw)
    start = raw.find("{")
    if start < 0:
        return None
    fragment = raw[start:]

    end = fragment.rfind("}")
    if end > 0:
        candidate = fragment[: end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # nesting 순서를 추적해서 올바른 순서로 닫기
    stack = []
    in_str = False
    escape = False
    for ch in fragment:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    if in_str:
        fragment += '"'

    for opener in reversed(stack):
        fragment += "}" if opener == "{" else "]"

    try:
        return json.loads(fragment)
    except json.JSONDecodeError:
        return None


class PlanningAgent:
    """Designs the complete book architecture before writing begins."""

    def __init__(self, provider: BaseProvider):
        self.llm = provider.get_chat_model(temperature=0.3, json_mode=True, max_tokens=4096)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        logger.info("PlanningAgent: Designing book architecture for '%s'", state["title"])

        source_summary = self._build_source_summary(state.get("source_materials", []))

        user_prompt = PLANNING_USER.format(
            title=state["title"],
            description=state.get("description", ""),
            num_chapters=state.get("num_chapters", 10),
            words_per_chapter=state.get("words_per_chapter", "3000-5000"),
            language=state.get("language", "English"),
            guidelines="\n".join(f"- {g}" for g in state.get("writing_guidelines", [])) or "None",
            source_summary=source_summary,
        )

        messages = [
            SystemMessage(content=PLANNING_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        plan_data = None
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.llm.invoke(messages)
                raw = response.content

                try:
                    plan_data = json.loads(_strip_markdown_fences(raw))
                except json.JSONDecodeError:
                    logger.warning("PlanningAgent: JSON parse failed (attempt %d), repairing", attempt)
                    plan_data = _repair_truncated_json(raw)

                if plan_data is not None:
                    break

                last_error = f"Could not parse JSON response (attempt {attempt}): {raw[:200]}"
                logger.warning("PlanningAgent: %s", last_error)

            except Exception as e:
                last_error = str(e)
                logger.warning("PlanningAgent: attempt %d failed: %s", attempt, e)

        if plan_data is None:
            logger.error("PlanningAgent: All attempts failed — returning empty plan. %s", last_error)
            return {**state, "book_plan": {}, "planned_chapters": []}

        book_plan = plan_data.get("book_plan", plan_data)
        logger.info("PlanningAgent: Plan complete — %d chapters", len(book_plan.get("chapters", [])))

        return {
            **state,
            "book_plan": book_plan,
            "core_themes": book_plan.get("core_themes", []),
            "target_audience": book_plan.get("target_audience", "General readers"),
            "tone": book_plan.get("tone", "Informative and engaging"),
            "glossary_terms": book_plan.get("glossary_terms", []),
            "cross_chapter_threads": book_plan.get("cross_chapter_threads", []),
            "planned_chapters": book_plan.get("chapters", []),
        }

    @staticmethod
    def _build_source_summary(materials: list[dict]) -> str:
        if not materials:
            return ""

        parts = ["\nSource materials (base your chapter structure on these):"]
        for i, m in enumerate(materials, 1):
            title = m.get("title", m.get("source_path", f"Source {i}"))
            content = m.get("content", "")[:3000]
            parts.append(f"\n--- Source {i}: {title} ---\n{content}")

        return "\n".join(parts)
