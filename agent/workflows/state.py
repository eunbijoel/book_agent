from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict
import operator


class BookState(TypedDict, total=False):
    # Book-level metadata
    title: str
    description: str
    language: str
    words_per_chapter: str
    num_chapters: int
    writing_guidelines: list[str]

    # TOC input (preserved through LangGraph state)
    toc_chapters: list[dict]

    # Planning agent output
    book_plan: dict[str, Any]
    planned_chapters: list[dict]
    core_themes: list[str]
    target_audience: str
    tone: str
    glossary_terms: list[str]
    cross_chapter_threads: list[str]

    # Chapter iteration state
    current_chapter: dict[str, Any]
    chapter_index: int

    # Per-chapter agent outputs
    current_research: dict[str, Any]
    current_draft: str
    first_draft: str
    draft_word_count: int
    current_review: dict[str, Any]
    review_requires_rewrite: bool
    edited_word_count: int
    current_evaluation: dict[str, Any]
    evaluation_score: float
    evaluation_verdict: str
    needs_rewrite: bool
    rewrite_count: int

    # Accumulator for completed chapters
    completed_chapters: Annotated[list[dict], operator.add]

    # Book-level output
    output_dir: str
    errors: Annotated[list[str], operator.add]
