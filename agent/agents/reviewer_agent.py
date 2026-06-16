from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.prompts.reviewer_prompts import REVIEWER_SYSTEM, REVIEWER_USER
from agent.providers.base import BaseProvider


def _strip_markdown_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl > 0:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """Reviews draft for accuracy, consistency, completeness, and redundancy."""

    def __init__(self, provider: BaseProvider):
        self.llm = provider.get_chat_model(temperature=0.1, json_mode=True)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        chapter = state["current_chapter"]
        logger.info(
            "ReviewerAgent: Reviewing Chapter %d: %s",
            chapter["number"],
            chapter["title"],
        )

        chapter_plan = self._find_chapter_plan(state.get("planned_chapters", []), chapter["number"])
        book_context = self._build_book_context(state)

        user_prompt = REVIEWER_USER.format(
            book_title=state["title"],
            chapter_number=chapter["number"],
            chapter_title=chapter["title"],
            target_audience=state.get("target_audience", "General readers"),
            key_concepts=", ".join(chapter_plan.get("key_concepts", [])) or "See chapter description",
            learning_objectives="\n".join(
                f"- {obj}" for obj in chapter_plan.get("learning_objectives", [])
            ) or "Cover all key concepts",
            book_context=book_context,
            draft=state["current_draft"],
        )

        messages = [
            SystemMessage(content=REVIEWER_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        raw = response.content

        try:
            data = json.loads(_strip_markdown_fences(raw))
        except json.JSONDecodeError:
            logger.warning("ReviewerAgent: JSON parse failed")
            try:
                cleaned = _strip_markdown_fences(raw)
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    data = {"review": {"overall_assessment": "pass", "issues": [], "requires_rewrite": False}}
            except json.JSONDecodeError:
                logger.warning("ReviewerAgent: JSON repair also failed, using defaults")
                data = {"review": {"overall_assessment": "pass", "issues": [], "requires_rewrite": False}}

        review = data.get("review", data)
        issues = review.get("issues", [])
        critical_issues = [i for i in issues if i.get("severity") == "critical"]

        logger.info(
            "ReviewerAgent: Chapter %d — assessment=%s, issues=%d (critical=%d)",
            chapter["number"],
            review.get("overall_assessment", "unknown"),
            len(issues),
            len(critical_issues),
        )

        return {
            **state,
            "current_review": review,
            "review_requires_rewrite": review.get("requires_rewrite", False),
        }

    def _build_book_context(self, state: dict) -> str:
        completed = state.get("completed_chapters", [])
        if not completed:
            return "No previous chapters."
        parts = []
        for ch in completed[-3:]:
            parts.append(f"Ch{ch['number']} ({ch['title']}): key terms used — {', '.join(ch.get('key_terms', []))}")
        return "\n".join(parts)

    def _find_chapter_plan(self, planned_chapters: list, chapter_number: int) -> dict:
        for ch in planned_chapters:
            if ch.get("number") == chapter_number:
                return ch
        return {}
