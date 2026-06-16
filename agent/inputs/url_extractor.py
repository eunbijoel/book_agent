from __future__ import annotations

import logging
import re
from typing import Any

from agent.inputs.base import BaseExtractor

logger = logging.getLogger(__name__)

_REMOVE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"}
_USER_AGENT = "BookAgent/1.0 (Content Extractor)"


class URLExtractor(BaseExtractor):
    """Extract readable text content from a URL."""

    def extract(self, url: str) -> dict[str, Any]:
        import httpx
        from bs4 import BeautifulSoup

        resp = httpx.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        title = self._extract_title(soup)
        metadata = self._extract_metadata(soup, url)

        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()

        body = self._extract_body(soup)
        text = self._clean_text(body.get_text(separator="\n"))

        if len(text) < 100:
            logger.warning("Extracted text very short (%d chars) from %s", len(text), url)

        chunks = self._chunk_text(text)

        return {
            "source_type": "url",
            "source_path": url,
            "title": title,
            "content": text[:50000],
            "content_length": len(text),
            "chunks": chunks,
            "metadata": metadata,
        }

    def _extract_title(self, soup) -> str:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()

        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    def _extract_metadata(self, soup, url: str) -> dict[str, str]:
        meta: dict[str, str] = {"url": url}

        author = soup.find("meta", attrs={"name": "author"})
        if author and author.get("content"):
            meta["author"] = author["content"]

        date = soup.find("meta", attrs={"name": re.compile(r"date|published", re.I)})
        if not date:
            date = soup.find("meta", property=re.compile(r"article:published", re.I))
        if date and date.get("content"):
            meta["date"] = date["content"]

        desc = soup.find("meta", attrs={"name": "description"})
        if not desc:
            desc = soup.find("meta", property="og:description")
        if desc and desc.get("content"):
            meta["description"] = desc["content"]

        return meta

    def _extract_body(self, soup):
        for tag_name in ("article", "main"):
            tag = soup.find(tag_name)
            if tag:
                return tag

        body = soup.find("body")
        return body if body else soup

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()
