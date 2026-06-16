from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agent.agents.planning_agent import PlanningAgent
from agent.providers.base import BaseProvider
from agent.workflows.chapter_workflow import build_chapter_workflow
from agent.workflows.state import BookState

logger = logging.getLogger(__name__)


def build_book_workflow(config: dict[str, Any]) -> Any:
    """Build the top-level book orchestration workflow."""

    provider: BaseProvider = config["provider"]

    planner = PlanningAgent(provider=provider)
    chapter_graph = build_chapter_workflow(config)

    def plan_node(state: BookState) -> BookState:
        logger.info("BookWorkflow: Running Planning Agent")
        return planner.run(state)

    def init_chapters_node(state: BookState) -> BookState:
        """Set up chapters from plan or TOC, initialize iteration state."""
        toc = state.get("toc_chapters", [])
        planned = state.get("planned_chapters", [])

        if toc and not planned:
            planned = toc
        elif toc and planned:
            # Planning Agent가 챕터를 생성했더라도 TOC 원본의 number/title을 유지하되
            # Planning Agent가 추가한 메타데이터(key_concepts 등)를 병합
            merged = []
            plan_by_num = {ch.get("number"): ch for ch in planned}
            for toc_ch in toc:
                num = toc_ch["number"]
                if num in plan_by_num:
                    merged_ch = {**plan_by_num[num], **toc_ch}
                    for key in ("key_concepts", "learning_objectives"):
                        if key in plan_by_num[num] and key not in toc_ch:
                            merged_ch[key] = plan_by_num[num][key]
                    merged.append(merged_ch)
                else:
                    merged.append(toc_ch)
            planned = merged

        if not planned:
            logger.error("BookWorkflow: No chapters found in plan or TOC")
            return {**state, "planned_chapters": [], "chapter_index": 0, "completed_chapters": [], "errors": ["No chapters found"]}

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

        if not chapters:
            logger.error("BookWorkflow: No chapters available — skipping to done")
            return {**state, "errors": [{"message": "No chapters to process"}]}

        if idx < len(chapters):
            current = chapters[idx]
            if "number" not in current:
                current["number"] = idx + 1
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

    def after_next_chapter(state: BookState) -> Literal["run_chapter", "done"]:
        """Only proceed to run_chapter if current_chapter was actually set."""
        if not state.get("current_chapter"):
            return "done"
        return "run_chapter"

    def more_chapters(state: BookState) -> Literal["next_chapter", "done"]:
        total = len(state.get("planned_chapters", []))
        if total == 0:
            return "done"
        idx = state.get("chapter_index", 0)
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
    graph.add_conditional_edges(
        "next_chapter",
        after_next_chapter,
        {"run_chapter": "run_chapter", "done": "done"},
    )
    graph.add_conditional_edges(
        "run_chapter",
        more_chapters,
        {"next_chapter": "next_chapter", "done": "done"},
    )
    graph.add_edge("done", END)

    return graph.compile()
