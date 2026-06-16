from __future__ import annotations

import re
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Base class for all source material extractors."""

    @abstractmethod
    def extract(self, source: str) -> dict:
        """Extract content from a source and return a standardised dict.

        Returns a dict with keys:
            source_type, source_path, title, content, content_length,
            chunks (list[dict]), metadata (dict).
        """

    def _chunk_text(self, text: str, chunk_size: int = 3000) -> list[dict]:
        """Split *text* into chunks of roughly *chunk_size* words,
        breaking at sentence boundaries when possible."""
        words = text.split()
        if not words:
            return []

        chunks: list[dict] = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            segment = " ".join(words[start:end])

            if end < len(words):
                last_period = segment.rfind(".")
                last_newline = segment.rfind("\n")
                break_pos = max(last_period, last_newline)
                if break_pos > len(segment) // 2:
                    segment = segment[: break_pos + 1]
                    end = start + len(segment.split())

            token_estimate = len(segment.split()) * 2 // 3
            chunks.append({
                "index": len(chunks),
                "text": segment,
                "token_estimate": token_estimate,
            })
            start = end

        return chunks
