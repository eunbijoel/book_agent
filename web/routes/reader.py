from __future__ import annotations

import json
import re
from pathlib import Path

import markdown
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.paths import OUTPUTS_DIR

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            return text[end + 3:].lstrip("\n")
    return text


def _list_chapters(book_dir: Path) -> list[dict]:
    chapters = []
    for p in sorted(book_dir.glob("chapter-*.md")):
        match = re.match(r"chapter-(\d+)", p.stem)
        if not match:
            continue
        num = int(match.group(1))
        raw = p.read_text(encoding="utf-8")
        content = _strip_frontmatter(raw)
        title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        title = title_match.group(1) if title_match else f"Chapter {num}"
        chapters.append({"number": num, "title": title, "path": p})
    return chapters


@router.get("/{slug}", response_class=HTMLResponse)
async def book_overview(request: Request, slug: str):
    book_dir = OUTPUTS_DIR / slug
    if not book_dir.exists():
        return HTMLResponse("<h1>Not found</h1>", status_code=404)

    chapters = _list_chapters(book_dir)
    report_path = book_dir / "book_report.json"
    report = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "slug": slug,
        "title": report.get("book_title", slug),
        "report": report,
        "chapters": chapters,
        "current_chapter": None,
        "chapter_html": None,
    })


@router.get("/{slug}/{chapter_num}", response_class=HTMLResponse)
async def read_chapter(request: Request, slug: str, chapter_num: int):
    book_dir = OUTPUTS_DIR / slug
    chapters = _list_chapters(book_dir)

    current = None
    for ch in chapters:
        if ch["number"] == chapter_num:
            current = ch
            break

    if not current:
        return HTMLResponse("<h1>Chapter not found</h1>", status_code=404)

    raw = current["path"].read_text(encoding="utf-8")
    content = _strip_frontmatter(raw)
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
    chapter_html = md.convert(content)

    report_path = book_dir / "book_report.json"
    report = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "slug": slug,
        "title": report.get("book_title", slug),
        "report": report,
        "chapters": chapters,
        "current_chapter": current,
        "chapter_html": chapter_html,
    })
