from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_sources(
    urls: list[str] | None = None,
    files: list[str] | None = None,
    mode: str = "topic",
) -> tuple[list[dict], str, dict[str, Any]]:
    """Extract source materials from URLs and/or files.

    Returns:
        (source_materials, source_mode, data_summary)
    """
    materials: list[dict] = []
    data_summary: dict[str, Any] = {}
    source_mode = "topic"

    if urls:
        from agent.inputs.url_extractor import URLExtractor

        extractor = URLExtractor()
        for url in urls:
            url = url.strip()
            if not url:
                continue
            try:
                result = extractor.extract(url)
                materials.append(result)
                logger.info("Extracted URL: %s (%d chars)", url, result.get("content_length", 0))
            except Exception as e:
                logger.warning("Failed to extract URL %s: %s", url, e)
        if materials:
            source_mode = "url"

    if files:
        from pathlib import Path

        for file_path in files:
            file_path = file_path.strip()
            if not file_path:
                continue

            suffix = Path(file_path).suffix.lower()

            if suffix in (".xlsx", ".xls", ".csv") and mode == "data-book":
                from agent.inputs.data_extractor import DataExtractor

                try:
                    extractor = DataExtractor()
                    result = extractor.extract(file_path)
                    materials.append(result)
                    data_summary = result.get("data_summary", {})
                    source_mode = "data"
                    logger.info("Extracted data file: %s", file_path)
                except Exception as e:
                    logger.warning("Failed to extract data file %s: %s", file_path, e)
            else:
                from agent.inputs.file_extractor import FileExtractor

                try:
                    extractor = FileExtractor()
                    result = extractor.extract(file_path)
                    materials.append(result)
                    if source_mode == "topic":
                        source_mode = "file"
                    logger.info("Extracted file: %s (%d chars)", file_path, result.get("content_length", 0))
                except Exception as e:
                    logger.warning("Failed to extract file %s: %s", file_path, e)

    return materials, source_mode, data_summary
