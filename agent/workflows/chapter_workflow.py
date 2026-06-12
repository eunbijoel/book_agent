from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agent.agents.research_agent import ResearchAgent
from agent.agents.writing_agent import WritingAgent
from agent.agents.reviewer_agent import ReviewerAgent
from agent.agents.editor_agent import EditorAgent
from agent.agents.evaluator_agent import EvaluatorAgent
from agent.workflows.state import BookState

logger = logging.getLogger(__name__)

MAX_REWRITES = 2


def build_chapter_workflow(config: dict[str, Any]) -> Any:
    """Build the per-chapter LangGraph workflow."""

    model = config.get("model", "llama3.2")
    base_url = config.get("base_url", "http://localhost:11434")

    research = ResearchAgent(model=model, base_url=base_url)
    writer = WritingAgent(model=model, base_url=base_url)
    reviewer = ReviewerAgent(model=model, base_url=base_url)
    editor = EditorAgent(model=model, base_url=base_url)
    evaluator = EvaluatorAgent(model=model, base_url=base_url)

    def research_node(state: BookState) -> BookState:
        return research.run(state)

    def write_node(state: BookState) -> BookState:
        return writer.run(state)

    def review_node(state: BookState) -> BookState:
        return reviewer.run(state)

    def edit_node(state: BookState) -> BookState:
        return editor.run(state)

    def evaluate_node(state: BookState) -> BookState:
        return evaluator.run(state)

    def after_review(state: BookState) -> Literal["edit", "write"]:
        """If reviewer flags critical issues and rewrites remain, go back to writer."""
        if state.get("review_requires_rewrite") and state.get("rewrite_count", 0) < MAX_REWRITES:
            logger.info(
                "Chapter %d: reviewer flagged rewrite (attempt %d/%d)",
                state["current_chapter"]["number"],
                state.get("rewrite_count", 0) + 1,
                MAX_REWRITES,
            )
            return "write"
        return "edit"

    def after_evaluate(state: BookState) -> Literal["write", "finalize"]:
        """If quality score is too low and rewrites remain, loop back to writer."""
        rewrite_count = state.get("rewrite_count", 0)
        if state.get("needs_rewrite") and rewrite_count < MAX_REWRITES:
            logger.info(
                "Chapter %d: score=%.1f below threshold, rewriting (attempt %d/%d)",
                state["current_chapter"]["number"],
                state.get("evaluation_score", 0),
                rewrite_count + 1,
                MAX_REWRITES,
            )
            return "write"
        return "finalize"

    def increment_rewrite(state: BookState) -> BookState:
        return {**state, "rewrite_count": state.get("rewrite_count", 0) + 1}

    def finalize_node(state: BookState) -> BookState:
        chapter = state["current_chapter"]
        logger.info(
            "Chapter %d finalized — score=%.1f words=%d",
            chapter["number"],
            state.get("evaluation_score", 0.0),
            state.get("edited_word_count", state.get("draft_word_count", 0)),
        )
        completed_entry = {
            "number": chapter["number"],
            "title": chapter["title"],
            "content": state["current_draft"],
            "first_draft": state.get("first_draft", state["current_draft"]),
            "word_count": state.get("edited_word_count", state.get("draft_word_count", 0)),
            "evaluation_score": state.get("evaluation_score", 0.0),
            "evaluation": state.get("current_evaluation", {}),
            "review": state.get("current_review", {}),
            "rewrite_count": state.get("rewrite_count", 0),
            "summary": _extract_summary(state["current_draft"]),
            "key_terms": state.get("glossary_terms", [])[:10],
        }
        return {
            **state,
            "completed_chapters": [completed_entry],
        }

    def _extract_summary(text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#")]
        first_para = " ".join(lines[:3]) if lines else ""
        return first_para[:300] + "..." if len(first_para) > 300 else first_para

    graph = StateGraph(BookState)

    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node)
    graph.add_node("increment_rewrite", increment_rewrite)
    graph.add_node("edit", edit_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "research")
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges(
        "review",
        after_review,
        {"write": "increment_rewrite", "edit": "edit"},
    )
    graph.add_edge("increment_rewrite", "write")
    graph.add_edge("edit", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        after_evaluate,
        {"write": "increment_rewrite", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
