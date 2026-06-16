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

    def __init__(self, output_dir: str, book_title: str, provider_name: str = "", model_name: str = ""):
        self.base_dir = Path(output_dir)
        self.book_slug = slugify(book_title, max_length=80)
        self.book_dir = self.base_dir / self.book_slug
        self.book_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.book_dir / ".progress.json"
        self.provider_name = provider_name
        self.model_name = model_name

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
            f"provider: {self.provider_name}\n"
            f"model: {self.model_name}\n"
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

    @staticmethod
    def _dedupe_completed_chapters(completed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the latest entry per chapter number."""
        by_number: dict[int, dict[str, Any]] = {}
        for ch in completed:
            by_number[int(ch["number"])] = ch
        return sorted(by_number.values(), key=lambda c: c["number"])

    def save_book_report(self, state: dict[str, Any]) -> Path:
        completed = self._dedupe_completed_chapters(state.get("completed_chapters", []))
        scores = [ch.get("evaluation_score", 0) for ch in completed if ch.get("evaluation_score")]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        total_words = sum(ch.get("word_count", 0) for ch in completed)

        report = {
            "book_title": state.get("title", ""),
            "provider": state.get("provider_name", "") or self.provider_name,
            "model": state.get("model_name", "") or self.model_name,
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

    def save_consolidated_outputs(self, state: dict[str, Any]) -> dict[str, Path]:
        title = state.get("title", "Untitled")
        completed = self._dedupe_completed_chapters(state.get("completed_chapters", []))
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        paths = {}

        def compile_book(chapters: list, content_key: str, version_label: str) -> str:
            lines = [f"# {title}\n", f"*{version_label} | Generated: {generated_at}*\n"]
            lines.append(f"**Chapters: {len(chapters)}**\n")
            lines.append("---\n")
            for ch in chapters:
                content = ch.get(content_key, ch.get("content", ""))
                lines.append(f"\n## Chapter {ch['number']}: {ch['title']}\n")
                lines.append(content)
                lines.append("\n\n---\n")
            return "\n".join(lines)

        book_v1 = compile_book(completed, "first_draft", "V1 - First Draft")
        paths["book_v1"] = self.book_dir / "book_v1.md"
        paths["book_v1"].write_text(book_v1, encoding="utf-8")

        book_v2 = compile_book(completed, "content", "V2 - Reviewed & Edited")
        paths["book_v2"] = self.book_dir / "book_v2.md"
        paths["book_v2"].write_text(book_v2, encoding="utf-8")

        final_lines = [f"# {title}\n", f"*Final Version | Generated: {generated_at}*\n"]
        final_lines.append("## Table of Contents\n")
        for ch in completed:
            final_lines.append(f"- Chapter {ch['number']}: {ch['title']}")
        final_lines.append("\n---\n")
        for ch in completed:
            final_lines.append(f"\n## Chapter {ch['number']}: {ch['title']}\n")
            final_lines.append(ch.get("content", ""))
            final_lines.append("\n\n---\n")
        paths["book_final"] = self.book_dir / "book_final.md"
        paths["book_final"].write_text("\n".join(final_lines), encoding="utf-8")

        scores = [ch.get("evaluation_score", 0) for ch in completed if ch.get("evaluation_score")]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        total_words = sum(ch.get("word_count", 0) for ch in completed)
        eval_lines = [f"# Evaluation Report: {title}\n", f"*Generated: {generated_at}*\n"]
        eval_lines.append("## Summary\n")
        eval_lines.append(f"| Metric | Value |")
        eval_lines.append(f"|--------|-------|")
        eval_lines.append(f"| Total Chapters | {len(completed)} |")
        eval_lines.append(f"| Total Words | {total_words:,} |")
        eval_lines.append(f"| Average Score | {avg_score:.1f}/100 |")
        eval_lines.append("")
        eval_lines.append("## Per-Chapter Scores\n")
        eval_lines.append("| Ch | Title | Score | Words | Rewrites | Verdict |")
        eval_lines.append("|----|-------|-------|-------|----------|---------|")
        for ch in completed:
            ev = ch.get("evaluation", {})
            verdict = ev.get("verdict", "N/A")
            eval_lines.append(
                f"| {ch['number']} | {ch['title'][:30]} | {ch.get('evaluation_score', 0):.1f} "
                f"| {ch.get('word_count', 0):,} | {ch.get('rewrite_count', 0)} | {verdict} |"
            )
        eval_lines.append("")
        for ch in completed:
            ev = ch.get("evaluation", {})
            eval_lines.append(f"\n### Chapter {ch['number']}: {ch['title']}\n")
            detailed = ev.get("detailed_feedback", {})
            if detailed:
                for dim, feedback in detailed.items():
                    eval_lines.append(f"- **{dim}**: {feedback}")
            improvements = ev.get("top_improvements", [])
            if improvements:
                eval_lines.append("\n**Top improvements:**")
                for imp in improvements:
                    eval_lines.append(f"- {imp}")
            eval_lines.append("")
        paths["evaluation_report"] = self.book_dir / "evaluation_report.md"
        paths["evaluation_report"].write_text("\n".join(eval_lines), encoding="utf-8")

        review_lines = [f"# Review Checklist: {title}\n", f"*Generated: {generated_at}*\n"]
        for ch in completed:
            rev = ch.get("review", {})
            review_lines.append(f"\n## Chapter {ch['number']}: {ch['title']}\n")
            assessment = rev.get("overall_assessment", "N/A")
            review_lines.append(f"**Assessment:** {assessment}\n")
            issues = rev.get("issues", [])
            if issues:
                review_lines.append("### Issues\n")
                for i, issue in enumerate(issues, 1):
                    severity = issue.get("severity", "minor").upper()
                    itype = issue.get("type", "general")
                    desc = issue.get("issue", "")
                    fix = issue.get("fix", "")
                    review_lines.append(f"{i}. **[{severity}]** ({itype}) {desc}")
                    if fix:
                        review_lines.append(f"   - Fix: {fix}")
            else:
                review_lines.append("No issues found.\n")
            strengths = rev.get("strengths", [])
            if strengths:
                review_lines.append("\n### Strengths\n")
                for s in strengths:
                    review_lines.append(f"- {s}")
            review_lines.append("")
        paths["review_checklist"] = self.book_dir / "review_checklist.md"
        paths["review_checklist"].write_text("\n".join(review_lines), encoding="utf-8")

        for name, path in paths.items():
            logger.info("Saved: %s", path)
        return paths
