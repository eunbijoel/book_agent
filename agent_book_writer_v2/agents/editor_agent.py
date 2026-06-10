from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from prompts.editor_prompts import EDITOR_SYSTEM, EDITOR_USER

logger = logging.getLogger(__name__)


class EditorAgent:
    """Polishes style, flow, and applies reviewer recommendations."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.4,
            num_ctx=8192,
        )

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        chapter = state["current_chapter"]
        logger.info(
            "EditorAgent: Editing Chapter %d: %s",
            chapter["number"],
            chapter["title"],
        )

        review = state.get("current_review", {})
        issues = review.get("issues", [])
        strengths = review.get("strengths", [])

        issues_text = self._format_issues(issues)
        strengths_text = "\n".join(f"- {s}" for s in strengths) if strengths else "None noted"

        user_prompt = EDITOR_USER.format(
            book_title=state["title"],
            chapter_number=chapter["number"],
            chapter_title=chapter["title"],
            tone=state.get("tone", "Informative and engaging"),
            target_audience=state.get("target_audience", "General readers"),
            language=state.get("language", "English"),
            review_issues=issues_text,
            review_strengths=strengths_text,
            draft=state["current_draft"],
            target_words=state.get("words_per_chapter", "3000-5000"),
        )

        messages = [
            SystemMessage(content=EDITOR_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        edited = response.content

        word_count = len(edited.split())
        logger.info("EditorAgent: Chapter %d edited — %d words", chapter["number"], word_count)

        return {
            **state,
            "current_draft": edited,
            "edited_word_count": word_count,
        }

    def _format_issues(self, issues: list) -> str:
        if not issues:
            return "No major issues identified."
        lines = []
        for i, issue in enumerate(issues, 1):
            severity = issue.get("severity", "minor")
            itype = issue.get("type", "general")
            fix = issue.get("fix", "")
            lines.append(f"{i}. [{severity.upper()}] {itype}: {fix}")
        return "\n".join(lines)
