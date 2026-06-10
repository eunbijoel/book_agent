from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from slugify import slugify

logger = logging.getLogger(__name__)


class OutputManager:
    """Handles file I/O for book chapters and progress tracking."""

    def __init__(self, output_dir: str, book_title: str):
        self.base_dir = Path(output_dir)
        self.book_slug = slugify(book_title, max_length=80)
        self.book_dir = self.base_dir / self.book_slug
        self.book_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.book_dir / ".progress.json"

    def save_chapter(self, chapter_data: dict[str, Any]) -> Path:
        num = chapter_data["number"]
        title = chapter_data["title"]
        content = chapter_data["content"]
        word_count = chapter_data.get("word_count", 0)
        score = chapter_data.get("evaluation_score", 0.0)
        rewrite_count = chapter_data.get("rewrite_count", 0)

        slug = slugify(title, max_length=60)
        filename = f"chapter-{num:02d}-{slug}.md"
        filepath = self.book_dir / filename

        front_matter = (
            f"---\n"
            f"chapter: {num}\n"
            f"title: \"{title}\"\n"
            f"word_count: {word_count}\n"
            f"quality_score: {score:.1f}\n"
            f"rewrite_count: {rewrite_count}\n"
            f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"---\n\n"
        )

        filepath.write_text(front_matter + content, encoding="utf-8")
        logger.info("Saved: %s (%d words, score=%.1f)", filename, word_count, score)

        if chapter_data.get("evaluation"):
            eval_path = self.book_dir / f"chapter-{num:02d}-evaluation.json"
            eval_path.write_text(
                json.dumps(chapter_data["evaluation"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return filepath

    def load_progress(self) -> dict:
        if self.progress_file.exists():
            return json.loads(self.progress_file.read_text(encoding="utf-8"))
        return {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed": [],
            "failed": {},
            "in_progress": None,
        }

    def save_progress(self, progress: dict) -> None:
        self.progress_file.write_text(
            json.dumps(progress, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save_book_report(self, state: dict[str, Any]) -> Path:
        completed = state.get("completed_chapters", [])
        scores = [ch.get("evaluation_score", 0) for ch in completed if ch.get("evaluation_score")]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        total_words = sum(ch.get("word_count", 0) for ch in completed)

        report = {
            "book_title": state.get("title", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_chapters": len(completed),
            "total_words": total_words,
            "average_quality_score": round(avg_score, 2),
            "chapter_scores": [
                {
                    "number": ch["number"],
                    "title": ch["title"],
                    "score": ch.get("evaluation_score", 0),
                    "word_count": ch.get("word_count", 0),
                    "rewrites": ch.get("rewrite_count", 0),
                }
                for ch in completed
            ],
            "book_plan": state.get("book_plan", {}),
        }

        report_path = self.book_dir / "book_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Book report saved: %s", report_path)
        return report_path
