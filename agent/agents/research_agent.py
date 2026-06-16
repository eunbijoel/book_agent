from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.prompts.research_prompts import RESEARCH_SYSTEM, RESEARCH_USER
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


class ResearchAgent:
    """Gathers facts, context, and references for a single chapter."""

    def __init__(self, provider: BaseProvider):
        self.llm = provider.get_chat_model(temperature=0.2, json_mode=True)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        chapter = state["current_chapter"]
        logger.info(
            "ResearchAgent: Researching Chapter %d: %s",
            chapter["number"],
            chapter["title"],
        )

        book_plan = state.get("book_plan", {})
        chapter_plan = self._find_chapter_plan(state.get("planned_chapters", []), chapter["number"])

        source_chunks = self._build_source_chunks(
            chapter_plan, state.get("source_materials", []),
        )

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
            source_chunks=source_chunks,
        )

        messages = [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        raw = response.content

        try:
            data = json.loads(_strip_markdown_fences(raw))
        except json.JSONDecodeError:
            logger.warning("ResearchAgent: JSON parse failed, attempting extraction")
            try:
                cleaned = _strip_markdown_fences(raw)
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    data = {"research": {"key_facts": [], "background_context": raw}}
            except json.JSONDecodeError:
                logger.warning("ResearchAgent: JSON repair also failed, using raw text")
                data = {"research": {"key_facts": [], "background_context": raw[:2000]}}

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

    @staticmethod
    def _build_source_chunks(chapter_plan: dict, materials: list[dict]) -> str:
        if not materials:
            return ""

        all_chunks = []
        for m in materials:
            for chunk in m.get("chunks", []):
                all_chunks.append({**chunk, "source_title": m.get("title", "")})

        if not all_chunks:
            content_parts = []
            for m in materials:
                content_parts.append(m.get("content", "")[:2000])
            if content_parts:
                return (
                    "\nReference materials (prioritise facts from these sources):\n"
                    + "\n---\n".join(content_parts)
                )
            return ""

        selected = _select_relevant_chunks(chapter_plan, all_chunks)
        if not selected:
            return ""

        parts = ["\nReference materials (prioritise facts from these sources):"]
        for chunk in selected:
            src = chunk.get("source_title", "")
            header = f"[{src}]" if src else ""
            parts.append(f"\n{header}\n{chunk['text'][:2000]}")

        return "\n".join(parts)


def _select_relevant_chunks(chapter_info: dict, all_chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Select chunks most relevant to the chapter by keyword matching."""
    keywords = list(chapter_info.get("key_concepts", []))
    keywords.append(chapter_info.get("title", ""))
    keywords = [k.lower() for k in keywords if k]

    if not keywords:
        return all_chunks[:top_k]

    scored = []
    for chunk in all_chunks:
        text_lower = chunk["text"].lower()
        score = sum(1 for kw in keywords if kw in text_lower)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]
