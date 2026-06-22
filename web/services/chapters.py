from __future__ import annotations

import re
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^#{1,2}\s+(.+)", re.MULTILINE)
CHAPTER_PREFIX_RE = re.compile(
    r"^(?:Chapter\s*)?\d+\s*장\s*[:.．]\s*"
    r"|^Chapter\s+\d+\s*[:.．]?\s*"
    r"|^\d+\s*장\s*[:.．]\s*"
    r"|^\d+\.\s*",
    re.IGNORECASE,
)


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def chapter_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if match:
        return text[match.end():].lstrip("\n")
    return text


def normalize_chapter_title(title: str) -> str:
    cleaned = title.strip()
    prev = None
    while cleaned and cleaned != prev:
        prev = cleaned
        cleaned = CHAPTER_PREFIX_RE.sub("", cleaned).strip()
    return cleaned


def heading_title(body: str) -> str:
    match = HEADING_RE.search(body)
    if not match:
        return ""
    return normalize_chapter_title(match.group(1))


def chapter_title(path: Path) -> str:
    """Single source of truth for chapter titles across book list and reader."""
    body = chapter_body(path)
    from_heading = heading_title(body)
    if from_heading:
        return from_heading

    meta = read_frontmatter(path)
    if meta.get("title"):
        return normalize_chapter_title(str(meta["title"]))

    stem = path.stem
    if stem.startswith("chapter-"):
        parts = stem.split("-", 2)
        if len(parts) >= 3:
            return parts[2].replace("-", " ")
    return stem


def list_chapter_files(book_dir: Path) -> list[Path]:
    return sorted(
        p for p in book_dir.glob("chapter-*.md")
        if "evaluation" not in p.name
        and "quantitative" not in p.name
        and "source" not in p.name
    )


def list_chapters(book_dir: Path) -> list[dict]:
    chapters = []
    for p in list_chapter_files(book_dir):
        match = re.match(r"chapter-(\d+)", p.stem)
        if not match:
            continue
        num = int(match.group(1))
        chapters.append({
            "number": num,
            "title": chapter_title(p),
            "path": p,
        })
    return chapters
