from __future__ import annotations

import re
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader

from web.services.books import scan_output_books


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            return text[end + 3:].lstrip("\n")
    return text


def _load_chapters(book_dir: Path) -> list[dict]:
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

        md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
        html = md.convert(content)

        chapters.append({
            "number": num,
            "title": title,
            "html": html,
        })
    return chapters


def generate_library(
    outputs_dir: Path,
    library_dir: Path,
    templates_dir: Path,
) -> Path:
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    index_tmpl = env.get_template("library_index.html")
    reader_tmpl = env.get_template("book_reader.html")

    books = []
    for meta in scan_output_books(outputs_dir):
        book_dir = outputs_dir / meta["slug"]
        chapters = _load_chapters(book_dir)
        if not chapters:
            continue

        book_info = {
            "slug": meta["slug"],
            "title": meta["title"],
            "total_chapters": meta["chapters"],
            "total_words": meta["words"],
            "avg_score": meta["score"],
            "generated_at": meta.get("generated_at", ""),
            "chapters": chapters,
        }
        books.append(book_info)

        book_out = library_dir / book_info["slug"]
        book_out.mkdir(parents=True, exist_ok=True)
        for ch in chapters:
            ch_html = reader_tmpl.render(book=book_info, chapter=ch, chapters=chapters)
            (book_out / f"chapter-{ch['number']:02d}.html").write_text(ch_html, encoding="utf-8")

    index_html = index_tmpl.render(books=books)
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / "index.html").write_text(index_html, encoding="utf-8")

    return library_dir
