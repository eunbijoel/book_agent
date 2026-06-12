from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from agent.prompts.planning_prompts import PLANNING_SYSTEM, PLANNING_USER

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def _repair_truncated_json(raw: str) -> dict | None:
    """Try to repair JSON that was truncated mid-generation."""
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

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.3,
            format="json",
            num_ctx=8192,
            num_predict=4096,
        )

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        logger.info("PlanningAgent: Designing book architecture for '%s'", state["title"])

        user_prompt = PLANNING_USER.format(
            title=state["title"],
            description=state.get("description", ""),
            num_chapters=state.get("num_chapters", 10),
            words_per_chapter=state.get("words_per_chapter", "3000-5000"),
            language=state.get("language", "English"),
            guidelines="\n".join(f"- {g}" for g in state.get("writing_guidelines", [])) or "None",
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
                    plan_data = json.loads(raw)
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
