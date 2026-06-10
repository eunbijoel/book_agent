from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from prompts.writing_prompts import WRITING_SYSTEM, WRITING_USER

logger = logging.getLogger(__name__)


class WritingAgent:
    """Generates the full prose draft for a chapter."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.7,
            num_ctx=8192,
        )

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        chapter = state["current_chapter"]
        logger.info(
            "WritingAgent: Writing Chapter %d: %s",
            chapter["number"],
            chapter["title"],
        )

        chapter_plan = self._find_chapter_plan(state.get("planned_chapters", []), chapter["number"])
        research = state.get("current_research", {})

        research_notes = self._format_research(research)
        previous_context = self._build_previous_context(state)

        user_prompt = WRITING_USER.format(
            chapter_number=chapter["number"],
            chapter_title=chapter["title"],
            book_title=state["title"],
            target_audience=state.get("target_audience", "General readers"),
            tone=state.get("tone", "Informative and engaging"),
            target_words=state.get("words_per_chapter", "3000-5000"),
            language=state.get("language", "English"),
            chapter_purpose=chapter_plan.get("purpose", chapter.get("description", "")),
            learning_objectives="\n".join(
                f"- {obj}" for obj in chapter_plan.get("learning_objectives", [])
            ) or "- Cover all key concepts thoroughly",
            key_concepts=", ".join(chapter_plan.get("key_concepts", [])) or "See chapter description",
            research_notes=research_notes,
            previous_context=previous_context,
            writing_guidelines="\n".join(
                f"- {g}" for g in state.get("writing_guidelines", [])
            ) or "None",
        )

        messages = [
            SystemMessage(content=WRITING_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        draft = response.content

        word_count = len(draft.split())
        logger.info("WritingAgent: Chapter %d draft — %d words", chapter["number"], word_count)

        return {
            **state,
            "current_draft": draft,
            "draft_word_count": word_count,
            "rewrite_count": state.get("rewrite_count", 0),
        }

    def _format_research(self, research: dict) -> str:
        if not research:
            return "No research notes available."
        parts = []
        if research.get("background_context"):
            parts.append(f"Context: {research['background_context']}")
        if research.get("key_facts"):
            parts.append("Key facts:\n" + "\n".join(f"- {f}" for f in research["key_facts"]))
        if research.get("suggested_examples"):
            parts.append("Examples to use:\n" + "\n".join(f"- {e}" for e in research["suggested_examples"]))
        if research.get("common_misconceptions"):
            parts.append("Misconceptions to address:\n" + "\n".join(f"- {m}" for m in research["common_misconceptions"]))
        return "\n\n".join(parts)

    def _build_previous_context(self, state: dict) -> str:
        completed = state.get("completed_chapters", [])
        if not completed:
            return "This is the first chapter."
        summaries = []
        for ch in completed[-2:]:
            summaries.append(f"Chapter {ch['number']} ({ch['title']}): {ch.get('summary', 'Covered core concepts.')}")
        return "\n".join(summaries)

    def _find_chapter_plan(self, planned_chapters: list, chapter_number: int) -> dict:
        for ch in planned_chapters:
            if ch.get("number") == chapter_number:
                return ch
        return {}
