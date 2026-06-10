from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agents.planning_agent import PlanningAgent
from workflows.chapter_workflow import build_chapter_workflow
from workflows.state import BookState

logger = logging.getLogger(__name__)


def build_book_workflow(config: dict[str, Any]) -> Any:
    """Build the top-level book orchestration workflow."""

    model = config.get("model", "llama3.2")
    base_url = config.get("base_url", "http://localhost:11434")

    planner = PlanningAgent(model=model, base_url=base_url)
    chapter_graph = build_chapter_workflow(config)

    def plan_node(state: BookState) -> BookState:
        logger.info("BookWorkflow: Running Planning Agent")
        return planner.run(state)

    def init_chapters_node(state: BookState) -> BookState:
        """Set up chapters from plan or TOC, initialize iteration state."""
        planned = state.get("planned_chapters", [])
        if not planned:
            planned = state.get("toc_chapters", [])

        logger.info("BookWorkflow: Starting chapter iteration — %d chapters", len(planned))
        return {
            **state,
            "planned_chapters": planned,
            "chapter_index": 0,
            "completed_chapters": [],
            "errors": [],
        }

    def next_chapter_node(state: BookState) -> BookState:
        """Advance to next chapter and set current_chapter."""
        idx = state.get("chapter_index", 0)
        chapters = state.get("planned_chapters", [])

        if idx < len(chapters):
            current = chapters[idx]
            logger.info(
                "BookWorkflow: Starting Chapter %d/%d: %s",
                idx + 1,
                len(chapters),
                current.get("title", ""),
            )
            return {
                **state,
                "current_chapter": current,
                "chapter_index": idx + 1,
                "current_research": {},
                "current_draft": "",
                "current_review": {},
                "current_evaluation": {},
                "rewrite_count": 0,
                "needs_rewrite": False,
                "review_requires_rewrite": False,
            }
        return state

    def run_chapter_node(state: BookState) -> BookState:
        """Invoke the full chapter sub-graph."""
        result = chapter_graph.invoke(state)
        return result

    def more_chapters(state: BookState) -> Literal["next_chapter", "done"]:
        idx = state.get("chapter_index", 0)
        total = len(state.get("planned_chapters", []))
        if idx < total:
            return "next_chapter"
        return "done"

    def done_node(state: BookState) -> BookState:
        completed = state.get("completed_chapters", [])
        scores = [ch.get("evaluation_score", 0) for ch in completed if ch.get("evaluation_score")]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        total_words = sum(ch.get("word_count", 0) for ch in completed)

        logger.info("=" * 60)
        logger.info("BOOK COMPLETE: %s", state.get("title", ""))
        logger.info("Chapters: %d | Avg quality score: %.1f | Total words: %d",
                    len(completed), avg_score, total_words)
        logger.info("=" * 60)

        return {
            **state,
            "book_complete": True,
            "average_score": avg_score,
            "total_words": total_words,
        }

    graph = StateGraph(BookState)

    graph.add_node("plan", plan_node)
    graph.add_node("init_chapters", init_chapters_node)
    graph.add_node("next_chapter", next_chapter_node)
    graph.add_node("run_chapter", run_chapter_node)
    graph.add_node("done", done_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "init_chapters")
    graph.add_edge("init_chapters", "next_chapter")
    graph.add_edge("next_chapter", "run_chapter")
    graph.add_conditional_edges(
        "run_chapter",
        more_chapters,
        {"next_chapter": "next_chapter", "done": "done"},
    )
    graph.add_edge("done", END)

    return graph.compile()
