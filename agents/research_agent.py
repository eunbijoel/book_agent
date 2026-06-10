from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from prompts.research_prompts import RESEARCH_SYSTEM, RESEARCH_USER

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Gathers facts, context, and references for a single chapter."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.2,
            format="json",
            num_ctx=8192,
        )

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        chapter = state["current_chapter"]
        logger.info(
            "ResearchAgent: Researching Chapter %d: %s",
            chapter["number"],
            chapter["title"],
        )

        book_plan = state.get("book_plan", {})
        chapter_plan = self._find_chapter_plan(state.get("planned_chapters", []), chapter["number"])

        user_prompt = RESEARCH_USER.format(
            book_title=state["title"],
            chapter_number=chapter["number"],
            chapter_title=chapter["title"],
            chapter_description=chapter.get("description", ""),
            chapter_purpose=chapter_plan.get("purpose", ""),
            key_concepts=", ".join(chapter_plan.get("key_concepts", [])) or "See chapter description",
            target_audience=state.get("target_audience", "General readers"),
            tone=state.get("tone", "Informative"),
            core_themes=", ".join(state.get("core_themes", [])),
        )

        messages = [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        raw = response.content

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ResearchAgent: JSON parse failed, attempting extraction")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                data = {"research": {"key_facts": [], "background_context": raw}}

        research = data.get("research", data)
        logger.info(
            "ResearchAgent: Found %d key facts for Chapter %d",
            len(research.get("key_facts", [])),
            chapter["number"],
        )

        return {
            **state,
            "current_research": research,
        }

    def _find_chapter_plan(self, planned_chapters: list, chapter_number: int) -> dict:
        for ch in planned_chapters:
            if ch.get("number") == chapter_number:
                return ch
        return {}
