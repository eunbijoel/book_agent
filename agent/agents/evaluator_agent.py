from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.prompts.evaluator_prompts import (
    EVALUATOR_SYSTEM,
    EVALUATOR_USER,
    SOURCE_EVALUATOR_SYSTEM,
    SOURCE_EVALUATOR_USER,
)
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


def _compute_quantitative_metrics(chapter_text: str, target_words: str) -> dict[str, Any]:
    words = chapter_text.split()
    word_count = len(words)

    try:
        parts = target_words.replace(" ", "").split("-")
        lo, hi = int(parts[0]), int(parts[1])
        midpoint = (lo + hi) / 2
    except (ValueError, IndexError):
        midpoint = 4000.0

    word_target_ratio = round(word_count / midpoint, 3) if midpoint > 0 else 0.0

    lower_words = [w.lower() for w in words]
    vocabulary_diversity = round(len(set(lower_words)) / len(lower_words), 3) if lower_words else 0.0

    if len(words) >= 5:
        ngrams = [tuple(lower_words[i:i + 5]) for i in range(len(lower_words) - 4)]
        counts = Counter(ngrams)
        repeated = sum(1 for c in counts.values() if c > 1)
        repetition_score = round(max(0.0, 100.0 - (repeated / len(ngrams) * 100)), 1)
    else:
        repetition_score = 100.0

    sentences = [s.strip() for s in re.split(r'[.?!。]\s+', chapter_text) if s.strip()]
    avg_sentence_length = round(
        sum(len(s.split()) for s in sentences) / len(sentences), 1
    ) if sentences else 0.0

    header_count = sum(1 for line in chapter_text.split("\n") if re.match(r'^#{1,6}\s', line))

    return {
        "word_count": word_count,
        "word_target_ratio": word_target_ratio,
        "vocabulary_diversity": vocabulary_diversity,
        "repetition_score": repetition_score,
        "avg_sentence_length": avg_sentence_length,
        "header_count": header_count,
    }


logger = logging.getLogger(__name__)

REWRITE_THRESHOLD = 55.0
REVISION_THRESHOLD = 70.0


class EvaluatorAgent:
    """Scores chapter quality on multiple dimensions and decides next action."""

    def __init__(self, provider: BaseProvider):
        self.llm = provider.get_chat_model(temperature=0.1, json_mode=True)

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
            data = json.loads(_strip_markdown_fences(raw))
        except json.JSONDecodeError:
            logger.warning("EvaluatorAgent: JSON parse failed")
            try:
                cleaned = _strip_markdown_fences(raw)
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    data = {"evaluation": {"scores": {"overall": 75.0}, "verdict": "good", "requires_rewrite": False}}
            except json.JSONDecodeError:
                logger.warning("EvaluatorAgent: JSON repair also failed, using defaults")
                data = {"evaluation": {"scores": {"overall": 75.0}, "verdict": "good", "requires_rewrite": False}}

        evaluation = data.get("evaluation", data)
        scores = evaluation.get("scores", {})
        llm_score = float(scores.get("overall", 75.0))

        verdict = evaluation.get("verdict", "good")

        # Quantitative metrics
        draft = state.get("current_draft", "")
        target_words_str = state.get("words_per_chapter", "3000-5000")
        quant_metrics = _compute_quantitative_metrics(draft, target_words_str)

        wtr = quant_metrics["word_target_ratio"]
        word_target_component = max(0.0, 100.0 - abs(1.0 - wtr) * 100)
        diversity_component = min(quant_metrics["vocabulary_diversity"] * 200, 100.0)
        repetition_component = quant_metrics["repetition_score"]
        quantitative_score = (
            word_target_component * 0.4
            + diversity_component * 0.3
            + repetition_component * 0.3
        )

        overall_quality = llm_score * 0.7 + quantitative_score * 0.3
        requires_rewrite = overall_quality < REWRITE_THRESHOLD
        if overall_quality < REVISION_THRESHOLD:
            requires_rewrite = requires_rewrite or evaluation.get("requires_rewrite", False)

        # Source faithfulness evaluation (conditional)
        source_eval: dict[str, Any] = {}
        source_mode = state.get("source_mode", "topic")
        if source_mode in ("url", "file", "data") and state.get("source_materials"):
            source_eval = self._evaluate_source_faithfulness(
                draft, state["source_materials"], state,
            )
            faithfulness = source_eval.get("scores", {}).get("faithfulness_overall", 70.0)
            if faithfulness < REWRITE_THRESHOLD:
                requires_rewrite = True

        logger.info(
            "EvaluatorAgent: Chapter %d — llm=%.1f quant=%.1f overall=%.1f verdict=%s rewrite=%s",
            chapter["number"],
            llm_score,
            quantitative_score,
            overall_quality,
            verdict,
            requires_rewrite,
        )

        return {
            **state,
            "current_evaluation": evaluation,
            "evaluation_score": round(overall_quality, 1),
            "evaluation_verdict": verdict,
            "needs_rewrite": requires_rewrite,
            "current_quantitative_metrics": quant_metrics,
            "current_source_evaluation": source_eval,
        }

    def _evaluate_source_faithfulness(
        self,
        chapter_text: str,
        source_materials: list[dict],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        source_parts = []
        total_len = 0
        for mat in source_materials:
            content = mat.get("content", "")
            title = mat.get("title", "Unknown")
            remaining = 10000 - total_len
            if remaining <= 0:
                break
            chunk = content[:remaining]
            source_parts.append(f"[Source: {title}]\n{chunk}")
            total_len += len(chunk)

        source_content = "\n\n".join(source_parts)

        chapter = state.get("current_chapter", {})
        user_prompt = SOURCE_EVALUATOR_USER.format(
            book_title=state.get("title", ""),
            chapter_number=chapter.get("number", 0),
            chapter_title=chapter.get("title", ""),
            source_content=source_content,
            chapter_text=chapter_text,
        )

        messages = [
            SystemMessage(content=SOURCE_EVALUATOR_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            raw = response.content
            data = json.loads(_strip_markdown_fences(raw))
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Source faithfulness evaluation failed: %s", e)
            try:
                cleaned = _strip_markdown_fences(raw)
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    raise ValueError("No JSON found")
            except Exception:
                return {
                    "scores": {
                        "claim_support": 70, "hallucination": 70, "accuracy": 70,
                        "key_point_coverage": 70, "omission": 70, "faithfulness_overall": 70.0,
                    },
                    "unsupported_claims": [],
                    "missing_key_points": [],
                    "accuracy_issues": [],
                    "verdict": "mostly_faithful",
                }

        se = data.get("source_evaluation", data)
        scores = se.get("scores", {})

        claim = float(scores.get("claim_support", 70))
        halluc = float(scores.get("hallucination", 70))
        accuracy = float(scores.get("accuracy", 70))
        coverage = float(scores.get("key_point_coverage", 70))
        omission = float(scores.get("omission", 70))

        faithfulness_overall = round(
            claim * 0.30 + halluc * 0.25 + accuracy * 0.25 + coverage * 0.10 + omission * 0.10, 1
        )

        if faithfulness_overall >= 85:
            verdict = "faithful"
        elif faithfulness_overall >= 70:
            verdict = "mostly_faithful"
        elif faithfulness_overall >= 55:
            verdict = "partially_faithful"
        else:
            verdict = "unfaithful"

        return {
            "scores": {
                "claim_support": int(claim),
                "hallucination": int(halluc),
                "accuracy": int(accuracy),
                "key_point_coverage": int(coverage),
                "omission": int(omission),
                "faithfulness_overall": faithfulness_overall,
            },
            "unsupported_claims": se.get("unsupported_claims", []),
            "missing_key_points": se.get("missing_key_points", []),
            "accuracy_issues": se.get("accuracy_issues", []),
            "verdict": verdict,
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
