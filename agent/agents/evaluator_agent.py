from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from agent.prompts.evaluator_prompts import EVALUATOR_SYSTEM, EVALUATOR_USER

logger = logging.getLogger(__name__)

REWRITE_THRESHOLD = 55.0
REVISION_THRESHOLD = 70.0


class EvaluatorAgent:
    """Scores chapter quality on multiple dimensions and decides next action."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.1,
            format="json",
            num_ctx=8192,
        )

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        chapter = state["current_chapter"]
        logger.info(
            "EvaluatorAgent: Evaluating Chapter %d: %s",
            chapter["number"],
            chapter["title"],
        )

        chapter_plan = self._find_chapter_plan(state.get("planned_chapters", []), chapter["number"])
        book_context = self._build_book_context(state)

        user_prompt = EVALUATOR_USER.format(
            book_title=state["title"],
            chapter_number=chapter["number"],
            chapter_title=chapter["title"],
            target_audience=state.get("target_audience", "General readers"),
            tone=state.get("tone", "Informative"),
            target_words=state.get("words_per_chapter", "3000-5000"),
            learning_objectives="\n".join(
                f"- {obj}" for obj in chapter_plan.get("learning_objectives", [])
            ) or "Cover all key concepts",
            key_concepts=", ".join(chapter_plan.get("key_concepts", [])) or "See chapter description",
            book_context=book_context,
            chapter=state["current_draft"],
        )

        messages = [
            SystemMessage(content=EVALUATOR_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        raw = response.content

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("EvaluatorAgent: JSON parse failed")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                data = {"evaluation": {"scores": {"overall": 75.0}, "verdict": "good", "requires_rewrite": False}}

        evaluation = data.get("evaluation", data)
        scores = evaluation.get("scores", {})
        overall = float(scores.get("overall", 75.0))

        verdict = evaluation.get("verdict", "good")
        requires_rewrite = overall < REWRITE_THRESHOLD or evaluation.get("requires_rewrite", False)

        logger.info(
            "EvaluatorAgent: Chapter %d — overall=%.1f verdict=%s rewrite=%s",
            chapter["number"],
            overall,
            verdict,
            requires_rewrite,
        )

        return {
            **state,
            "current_evaluation": evaluation,
            "evaluation_score": overall,
            "evaluation_verdict": verdict,
            "needs_rewrite": requires_rewrite,
        }

    def _build_book_context(self, state: dict) -> str:
        completed = state.get("completed_chapters", [])
        if not completed:
            return "This is the first chapter."
        parts = []
        for ch in completed[-3:]:
            score = ch.get("evaluation_score", "N/A")
            parts.append(f"Ch{ch['number']} ({ch['title']}): score={score}")
        return "\n".join(parts)

    def _find_chapter_plan(self, planned_chapters: list, chapter_number: int) -> dict:
        for ch in planned_chapters:
            if ch.get("number") == chapter_number:
                return ch
        return {}
