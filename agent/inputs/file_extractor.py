from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent.inputs.base import BaseExtractor

logger = logging.getLogger(__name__)

_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
_ENCODINGS = ("utf-8", "cp949", "latin-1")
_SUPPORTED = {".txt", ".md", ".pdf", ".docx"}


class FileExtractor(BaseExtractor):
    """Extract text from local files (TXT, MD, PDF, DOCX)."""

    def extract(self, source: str) -> dict[str, Any]:
        path = Path(source)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {source}")

        if path.stat().st_size > _MAX_FILE_SIZE:
            raise ValueError(f"File too large (>100 MB): {source}")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED:
            raise ValueError(f"Unsupported format: {suffix}. Supported: {', '.join(sorted(_SUPPORTED))}")

        if suffix in (".txt", ".md"):
            text, title = self._extract_text(path)
        elif suffix == ".pdf":
            text, title = self._extract_pdf(path)
        elif suffix == ".docx":
            text, title = self._extract_docx(path)
        else:
            raise ValueError(f"Unsupported format: {suffix}")

        if len(text) < 100:
            logger.warning("Extracted text very short (%d chars) from %s", len(text), source)

        chunks = self._chunk_text(text)

        return {
            "source_type": suffix.lstrip("."),
            "source_path": str(path),
            "title": title or path.stem,
            "content": text[:50000],
            "content_length": len(text),
            "chunks": chunks,
            "metadata": {
                "file_name": path.name,
                "file_size": path.stat().st_size,
            },
        }

    def _extract_text(self, path: Path) -> tuple[str, str]:
        text = self._read_with_fallback(path)
        title = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                if stripped.startswith("# "):
                    title = stripped[2:].strip()
                else:
                    title = stripped[:100]
                break
        return text, title

    def _extract_pdf(self, path: Path) -> tuple[str, str]:
        import pdfplumber

        pages: list[str] = []
        title = ""
        with pdfplumber.open(path) as pdf:
            if pdf.metadata and pdf.metadata.get("Title"):
                title = pdf.metadata["Title"]

            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text)

                for table in page.extract_tables():
                    rows = []
                    for row in table:
                        cells = [str(c) if c is not None else "" for c in row]
                        rows.append(" | ".join(cells))
                    if rows:
                        pages.append("\n".join(rows))

        text = "\n\n".join(pages)
        return text, title

    def _extract_docx(self, path: Path) -> tuple[str, str]:
        from docx import Document

        doc = Document(str(path))

        title = ""
        if doc.core_properties.title:
            title = doc.core_properties.title

        paragraphs: list[str] = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)

        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(" | ".join(cells))
            if rows:
                paragraphs.append("\n".join(rows))

        text = "\n\n".join(paragraphs)
        if not title and paragraphs:
            title = paragraphs[0][:100]
        return text, title

    def _read_with_fallback(self, path: Path) -> str:
        for enc in _ENCODINGS:
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return path.read_text(encoding="utf-8", errors="replace")
