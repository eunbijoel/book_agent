from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from web.paths import OUTPUTS_DIR
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _list_chapter_files(book_dir: Path) -> list[Path]:
    return sorted(
        p for p in book_dir.glob("chapter-*.md")
        if "evaluation" not in p.name
    )


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _infer_title(book_dir: Path, report: dict | None) -> str:
    if report and report.get("book_title"):
        return report["book_title"]

    mkdocs_path = book_dir / "site" / "mkdocs.yml"
    if mkdocs_path.exists():
        try:
            data = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8")) or {}
            if data.get("site_name"):
                return data["site_name"]
        except yaml.YAMLError:
            pass

    return book_dir.name.replace("-", " ")


def _stats_from_chapters(chapter_files: list[Path]) -> tuple[int, float, str]:
    total_words = 0
    scores: list[float] = []
    generated_at = ""

    for path in chapter_files:
        meta = _read_frontmatter(path)
        total_words += int(meta.get("word_count", 0) or 0)
        if meta.get("quality_score") is not None:
            scores.append(float(meta["quality_score"]))
        ts = str(meta.get("generated_at", "") or "")
        if ts and ts > generated_at:
            generated_at = ts

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return total_words, avg_score, generated_at


def _find_book_dirs(root: Path) -> list[Path]:
    """Find directories containing chapter markdown files, at any depth."""
    dirs: list[Path] = []
    for path in sorted(root.rglob("chapter-*.md")):
        d = path.parent
        if d not in dirs:
            dirs.append(d)
    return dirs


def scan_output_books(outputs_dir: Path | None = None) -> list[dict]:
    """List books under outputs/ that have at least one chapter markdown file."""
    root = outputs_dir or OUTPUTS_DIR
    if not root.exists():
        return []

    books: list[dict] = []
    for book_dir in _find_book_dirs(root):
        chapter_files = _list_chapter_files(book_dir)
        if not chapter_files:
            continue

        report: dict = {}
        report_path = book_dir / "book_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                report = {}

        words, score, generated_at = _stats_from_chapters(chapter_files)
        chapter_count = len(chapter_files)

        # Prefer chapter files over book_report.json — corrupted reports can
        # inflate counts when LangGraph state accumulates duplicate entries.
        report_chapters = report.get("total_chapters")
        report_words = report.get("total_words")
        use_report_stats = (
            report_chapters == chapter_count
            and report_words is not None
            and abs(int(report_words) - words) <= max(words, 1) * 0.1
        )

        rel = book_dir.relative_to(root)
        slug = str(rel).replace("\\", "/")

        books.append({
            "slug": slug,
            "title": _infer_title(book_dir, report),
            "chapters": report_chapters if use_report_stats else chapter_count,
            "words": report_words if use_report_stats else words,
            "score": report.get("average_quality_score", score),
            "generated_at": report.get("generated_at", generated_at),
            "provider": report.get("provider", ""),
            "model": report.get("model", ""),
        })

    return books
