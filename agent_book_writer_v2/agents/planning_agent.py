from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from prompts.planning_prompts import PLANNING_SYSTEM, PLANNING_USER

logger = logging.getLogger(__name__)


class PlanningAgent:
    """Designs the complete book architecture before writing begins."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.3,
            format="json",
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

        response = self.llm.invoke(messages)
        raw = response.content

        try:
            plan_data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("PlanningAgent: JSON parse failed, attempting extraction")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                plan_data = json.loads(raw[start:end])
            else:
                raise ValueError(f"PlanningAgent returned non-JSON: {raw[:200]}")

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
