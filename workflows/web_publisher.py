from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

MKDOCS_TEMPLATE = {
    "site_name": "",
    "theme": {
        "name": "material",
        "language": "ko",
        "palette": [
            {
                "scheme": "default",
                "primary": "indigo",
                "accent": "amber",
                "toggle": {
                    "icon": "material/brightness-7",
                    "name": "다크 모드로 전환",
                },
            },
            {
                "scheme": "slate",
                "primary": "indigo",
                "accent": "amber",
                "toggle": {
                    "icon": "material/brightness-4",
                    "name": "라이트 모드로 전환",
                },
            },
        ],
        "features": [
            "navigation.instant",
            "navigation.tracking",
            "navigation.expand",
            "toc.integrate",
            "navigation.top",
        ],
        "font": {"text": "Noto Sans KR", "code": "Roboto Mono"},
    },
    "markdown_extensions": [
        "admonition",
        "pymdownx.details",
        "pymdownx.superfences",
        "attr_list",
        "md_in_html",
        "toc",
    ],
    "plugins": ["search"],
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _strip_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end():]


def _build_index(
    book_title: str,
    description: str,
    chapters: list[dict[str, Any]],
    language: str,
) -> str:
    lines = [f"# {book_title}\n"]
    if description:
        lines.append(f"*{description}*\n")

    lang_label = "챕터" if language.lower() in ("korean", "ko") else "Chapters"
    word_label = "총 단어 수" if language.lower() in ("korean", "ko") else "Total words"
    score_label = "평균 품질" if language.lower() in ("korean", "ko") else "Avg. quality"

    total_words = sum(ch.get("word_count", 0) for ch in chapters)
    scores = [ch["score"] for ch in chapters if ch.get("score")]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **{lang_label}** | {len(chapters)} |")
    lines.append(f"| **{word_label}** | {total_words:,} |")
    if avg_score > 0:
        lines.append(f"| **{score_label}** | {avg_score:.1f} / 100 |")
    lines.append("")

    toc_label = "목차" if language.lower() in ("korean", "ko") else "Table of Contents"
    lines.append(f"## {toc_label}\n")
    for ch in chapters:
        num = ch["number"]
        title = ch["title"]
        slug = ch["filename"]
        lines.append(f"{num}. [{title}](chapters/{slug})")
    lines.append("")

    return "\n".join(lines)


class WebPublisher:

    def __init__(self, site_dir: Path | str):
        self.site_dir = Path(site_dir)
        self.docs_dir = self.site_dir / "docs"
        self.chapters_dir = self.docs_dir / "chapters"

    def publish_from_state(self, state: dict[str, Any]) -> Path:
        title = state.get("title", "Untitled")
        description = state.get("description", "")
        language = state.get("language", "Korean")
        completed = sorted(
            state.get("completed_chapters", []), key=lambda c: c["number"]
        )

        self._prepare_dirs()

        chapter_infos = []
        for ch in completed:
            content = ch.get("content", "")
            num = ch["number"]
            ch_title = ch["title"]
            from slugify import slugify
            slug = slugify(ch_title, max_length=60)
            filename = f"chapter-{num:02d}-{slug}.md"

            chapter_md = f"# {ch_title}\n\n{content}"
            (self.chapters_dir / filename).write_text(chapter_md, encoding="utf-8")

            chapter_infos.append({
                "number": num,
                "title": ch_title,
                "filename": filename,
                "word_count": ch.get("word_count", 0),
                "score": ch.get("evaluation_score", 0),
            })

        self._write_index(title, description, chapter_infos, language)
        self._write_mkdocs_yml(title, chapter_infos, language)

        logger.info("Web site generated at %s", self.site_dir)
        return self.site_dir

    def publish_from_files(self, book_dir: Path | str) -> Path:
        book_dir = Path(book_dir)
        if not book_dir.exists():
            raise FileNotFoundError(f"Book directory not found: {book_dir}")

        chapter_files = sorted(book_dir.glob("chapter-*[!evaluation]*.md"))
        if not chapter_files:
            raise FileNotFoundError(f"No chapter files found in {book_dir}")

        report_path = book_dir / "book_report.json"
        report = {}
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))

        book_title = report.get("book_title", book_dir.name.replace("-", " ").title())
        description = report.get("description", "")

        self._prepare_dirs()

        chapter_infos = []
        for fpath in chapter_files:
            raw = fpath.read_text(encoding="utf-8")
            meta, body = _strip_frontmatter(raw)

            num = meta.get("chapter", 0)
            ch_title = meta.get("title", f"Chapter {num}")
            word_count = meta.get("word_count", 0)
            score = meta.get("quality_score", 0)

            if num == 0:
                m = re.search(r"chapter-(\d+)", fpath.name)
                if m:
                    num = int(m.group(1))

            dest = self.chapters_dir / fpath.name
            dest.write_text(body, encoding="utf-8")

            chapter_infos.append({
                "number": num,
                "title": ch_title,
                "filename": fpath.name,
                "word_count": word_count,
                "score": score,
            })

        chapter_infos.sort(key=lambda c: c["number"])
        language = self._detect_language(chapter_infos, book_title)
        self._write_index(book_title, description, chapter_infos, language)
        self._write_mkdocs_yml(book_title, chapter_infos, language)

        logger.info("Web site generated at %s", self.site_dir)
        return self.site_dir

    def _prepare_dirs(self) -> None:
        if self.docs_dir.exists():
            shutil.rmtree(self.docs_dir)
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

    def _write_index(
        self,
        title: str,
        description: str,
        chapters: list[dict],
        language: str,
    ) -> None:
        index_md = _build_index(title, description, chapters, language)
        (self.docs_dir / "index.md").write_text(index_md, encoding="utf-8")

    def _write_mkdocs_yml(
        self,
        title: str,
        chapters: list[dict],
        language: str,
    ) -> None:
        config = dict(MKDOCS_TEMPLATE)
        config["site_name"] = title

        if language.lower() in ("korean", "ko"):
            config["theme"] = dict(config["theme"])
            config["theme"]["language"] = "ko"
        else:
            config["theme"] = dict(config["theme"])
            config["theme"]["language"] = "en"

        nav: list[dict[str, str]] = [{"Home": "index.md"}]
        for ch in chapters:
            label = f"Ch.{ch['number']}  {ch['title']}"
            nav.append({label: f"chapters/{ch['filename']}"})
        config["nav"] = nav

        yml_path = self.site_dir / "mkdocs.yml"
        yml_path.write_text(
            yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _detect_language(chapters: list[dict], title: str) -> str:
        sample = title + " ".join(ch["title"] for ch in chapters[:3])
        if re.search(r"[가-힣]", sample):
            return "Korean"
        return "English"
