from __future__ import annotations

import json
import re
from pathlib import Path

import markdown
import yaml
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from web.paths import OUTPUTS_DIR
from web.services.chapters import (
    HEADING_RE,
    chapter_title,
    list_chapters,
    normalize_chapter_title,
    read_frontmatter,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


class ChapterSaveBody(BaseModel):
    content: str


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            return text[end + 3:].lstrip("\n")
    return text


def _list_chapters(book_dir: Path) -> list[dict]:
    return list_chapters(book_dir)


def _load_report(book_dir: Path) -> dict:
    report_path = book_dir / "book_report.json"
    if report_path.exists():
        try:
            return json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


@router.get("/{slug:path}", response_class=HTMLResponse)
async def book_or_chapter(request: Request, slug: str):
    parts = slug.rsplit("/", 1)
    if len(parts) == 2 and parts[1].isdigit():
        book_slug, chapter_num = parts[0], int(parts[1])
        book_dir = OUTPUTS_DIR / book_slug
        if book_dir.is_dir():
            return _render_chapter(request, book_slug, book_dir, chapter_num)

    book_dir = OUTPUTS_DIR / slug
    if not book_dir.exists():
        return HTMLResponse("<h1>Not found</h1>", status_code=404)

    chapters = _list_chapters(book_dir)
    report = _load_report(book_dir)

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "slug": slug,
        "title": report.get("book_title", slug),
        "report": report,
        "chapters": chapters,
        "current_chapter": None,
        "chapter_html": None,
    })


def _render_chapter(request: Request, slug: str, book_dir: Path, chapter_num: int):
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

    report = _load_report(book_dir)

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "slug": slug,
        "title": report.get("book_title", slug),
        "report": report,
        "chapters": chapters,
        "current_chapter": current,
        "chapter_html": chapter_html,
        "chapter_raw": content,
    })


def _extract_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            fm_str = text[3:end].strip()
            body = text[end + 3:].lstrip("\n")
            try:
                fm = yaml.safe_load(fm_str) or {}
            except yaml.YAMLError:
                fm = {}
            return fm, body
    return {}, text


def _count_words(text: str) -> int:
    cleaned = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"[*_`~\[\]()>|#\-]", " ", cleaned)
    return len(cleaned.split())


def _rebuild_chapter_file(frontmatter: dict, content: str) -> str:
    fm_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{fm_str}\n---\n\n{content}"


def _update_book_report(book_dir: Path) -> None:
    report_path = book_dir / "book_report.json"
    if not report_path.exists():
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    total_words = 0
    for ch_path in sorted(book_dir.glob("chapter-*.md")):
        if "evaluation" in ch_path.stem or "quantitative" in ch_path.stem or "source" in ch_path.stem:
            continue
        raw = ch_path.read_text(encoding="utf-8")
        _, body = _extract_frontmatter(raw)
        total_words += _count_words(body)

    report["total_words"] = total_words
    for ch_score in report.get("chapter_scores", []):
        ch_num = ch_score["number"]
        ch_path = None
        for p in book_dir.glob(f"chapter-{ch_num:02d}*.md"):
            if "evaluation" not in p.stem and "quantitative" not in p.stem and "source" not in p.stem:
                ch_path = p
                break
        if ch_path and ch_path.exists():
            ch_score["word_count"] = _count_words(_strip_frontmatter(
                ch_path.read_text(encoding="utf-8")
            ))
            ch_score["title"] = chapter_title(ch_path)

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


@router.post("/{slug:path}/{chapter_num:int}/save")
async def save_chapter(slug: str, chapter_num: int, body: ChapterSaveBody):
    book_dir = (OUTPUTS_DIR / slug).resolve()
    if not str(book_dir).startswith(str(OUTPUTS_DIR.resolve())):
        return JSONResponse({"ok": False, "error": "invalid path"}, status_code=400)
    if not book_dir.is_dir():
        return JSONResponse({"ok": False, "error": "book not found"}, status_code=404)

    chapter_path = None
    for p in sorted(book_dir.glob(f"chapter-{chapter_num:02d}*.md")):
        if "evaluation" not in p.stem and "quantitative" not in p.stem and "source" not in p.stem:
            chapter_path = p
            break

    if not chapter_path or not chapter_path.exists():
        return JSONResponse({"ok": False, "error": "chapter not found"}, status_code=404)

    if not body.content.strip():
        return JSONResponse({"ok": False, "error": "empty content"}, status_code=400)

    raw = chapter_path.read_text(encoding="utf-8")
    fm, _ = _extract_frontmatter(raw)

    new_word_count = _count_words(body.content)
    fm["word_count"] = new_word_count

    title_match = HEADING_RE.search(body.content)
    if title_match:
        fm["title"] = normalize_chapter_title(title_match.group(1))

    new_file = _rebuild_chapter_file(fm, body.content)
    chapter_path.write_text(new_file, encoding="utf-8")

    _update_book_report(book_dir)

    return {"ok": True, "word_count": new_word_count}
