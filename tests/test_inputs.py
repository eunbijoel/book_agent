"""Tests for the input extraction pipeline (Phase 3-5)."""
from __future__ import annotations

import csv
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --------------- BaseExtractor ---------------


class TestBaseExtractor:
    def test_chunk_text_short(self):
        from agent.inputs.base import BaseExtractor

        class Dummy(BaseExtractor):
            def extract(self, source):
                return {}

        ext = Dummy()
        chunks = ext._chunk_text("hello world foo bar")
        assert len(chunks) == 1
        assert chunks[0]["index"] == 0
        assert "hello" in chunks[0]["text"]

    def test_chunk_text_splits_long(self):
        from agent.inputs.base import BaseExtractor

        class Dummy(BaseExtractor):
            def extract(self, source):
                return {}

        ext = Dummy()
        text = " ".join(["word"] * 7000)
        chunks = ext._chunk_text(text, chunk_size=3000)
        assert len(chunks) >= 2

    def test_chunk_text_empty(self):
        from agent.inputs.base import BaseExtractor

        class Dummy(BaseExtractor):
            def extract(self, source):
                return {}

        ext = Dummy()
        assert ext._chunk_text("") == []


# --------------- URLExtractor ---------------


class TestURLExtractor:
    def test_parse_html(self):
        from agent.inputs.url_extractor import URLExtractor

        ext = URLExtractor()
        html = textwrap.dedent("""
        <html>
        <head><title>Test Page</title></head>
        <body>
            <nav>Navigation</nav>
            <article>
                <h1>Article Title</h1>
                <p>First paragraph with content.</p>
                <p>Second paragraph with more content.</p>
            </article>
            <footer>Footer</footer>
        </body>
        </html>
        """)

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = ext.extract("https://example.com/test")

        assert result["source_type"] == "url"
        assert result["title"] == "Test Page"
        assert "Article Title" in result["content"]
        assert "First paragraph" in result["content"]
        assert "Navigation" not in result["content"]
        assert "Footer" not in result["content"]
        assert result["metadata"]["url"] == "https://example.com/test"

    def test_extract_metadata(self):
        from agent.inputs.url_extractor import URLExtractor

        ext = URLExtractor()
        html = textwrap.dedent("""
        <html>
        <head>
            <meta property="og:title" content="OG Title">
            <meta name="author" content="Author Name">
            <meta name="description" content="Page description">
        </head>
        <body><p>Content</p></body>
        </html>
        """)

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            result = ext.extract("https://example.com")

        assert result["title"] == "OG Title"
        assert result["metadata"]["author"] == "Author Name"
        assert result["metadata"]["description"] == "Page description"


# --------------- FileExtractor ---------------


class TestFileExtractor:
    def test_extract_txt(self, tmp_path):
        from agent.inputs.file_extractor import FileExtractor

        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is a test document.\n" * 10, encoding="utf-8")

        ext = FileExtractor()
        result = ext.extract(str(txt_file))

        assert result["source_type"] == "txt"
        assert "test document" in result["content"]
        assert result["content_length"] > 0

    def test_extract_md(self, tmp_path):
        from agent.inputs.file_extractor import FileExtractor

        md_file = tmp_path / "test.md"
        md_file.write_text("# My Title\n\nSome markdown content.\n" * 5, encoding="utf-8")

        ext = FileExtractor()
        result = ext.extract(str(md_file))

        assert result["source_type"] == "md"
        assert result["title"] == "My Title"

    def test_unsupported_format(self, tmp_path):
        from agent.inputs.file_extractor import FileExtractor

        f = tmp_path / "test.xyz"
        f.write_text("data")

        ext = FileExtractor()
        with pytest.raises(ValueError, match="Unsupported format"):
            ext.extract(str(f))

    def test_file_not_found(self):
        from agent.inputs.file_extractor import FileExtractor

        ext = FileExtractor()
        with pytest.raises(FileNotFoundError):
            ext.extract("/nonexistent/file.txt")

    def test_file_too_large(self, tmp_path):
        from agent.inputs.file_extractor import FileExtractor

        f = tmp_path / "huge.txt"
        f.write_bytes(b"x" * (101 * 1024 * 1024))

        ext = FileExtractor()
        with pytest.raises(ValueError, match="too large"):
            ext.extract(str(f))


# --------------- DataExtractor ---------------


class TestDataExtractor:
    def test_extract_csv(self, tmp_path):
        pytest.importorskip("pandas")
        from agent.inputs.data_extractor import DataExtractor

        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "value", "category"])
            for i in range(100):
                writer.writerow([f"item_{i}", i * 10, "A" if i % 2 == 0 else "B"])

        ext = DataExtractor()
        result = ext.extract(str(csv_file))

        assert result["source_type"] == "csv"
        assert result["data_summary"]["shape"]["rows"] == 100
        assert result["data_summary"]["shape"]["columns"] == 3
        assert len(result["chunks"]) >= 1
        assert "value" in result["metadata"]["columns"]

    def test_data_summary_structure(self, tmp_path):
        pytest.importorskip("pandas")
        from agent.inputs.data_extractor import DataExtractor

        csv_file = tmp_path / "simple.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x", "y"])
            for i in range(10):
                writer.writerow([i, i * 2])

        ext = DataExtractor()
        result = ext.extract(str(csv_file))

        summary = result["data_summary"]
        assert "columns" in summary
        col_x = next(c for c in summary["columns"] if c["name"] == "x")
        assert "stats" in col_x
        assert "mean" in col_x["stats"]

    def test_empty_dataset(self, tmp_path):
        pytest.importorskip("pandas")
        from agent.inputs.data_extractor import DataExtractor

        csv_file = tmp_path / "empty.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["col1", "col2"])

        ext = DataExtractor()
        with pytest.raises(ValueError, match="Empty dataset"):
            ext.extract(str(csv_file))


# --------------- Factory function ---------------


class TestExtractSources:
    def test_empty_returns_defaults(self):
        from agent.inputs import extract_sources

        materials, mode, data_summary = extract_sources()
        assert materials == []
        assert mode == "topic"
        assert data_summary == {}

    def test_file_extraction(self, tmp_path):
        from agent.inputs import extract_sources

        f = tmp_path / "note.txt"
        f.write_text("Content for testing the extraction pipeline.\n" * 5)

        materials, mode, data_summary = extract_sources(files=[str(f)])
        assert len(materials) == 1
        assert mode == "file"
        assert materials[0]["source_type"] == "txt"

    def test_url_extraction_with_mock(self):
        from agent.inputs import extract_sources

        html = "<html><head><title>T</title></head><body><p>Some content here.</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            materials, mode, _ = extract_sources(urls=["https://example.com"])

        assert len(materials) == 1
        assert mode == "url"

    def test_bad_url_skipped(self):
        from agent.inputs import extract_sources

        with patch("httpx.get", side_effect=Exception("Connection error")):
            materials, mode, _ = extract_sources(urls=["https://bad.url"])

        assert materials == []
        assert mode == "topic"


# --------------- Agent integration ---------------


class TestAgentSourceIntegration:
    def test_planning_agent_source_summary(self):
        from agent.agents.planning_agent import PlanningAgent

        summary = PlanningAgent._build_source_summary([])
        assert summary == ""

        materials = [{
            "title": "Test Doc",
            "content": "This is the content of the document." * 10,
            "source_path": "/test.txt",
        }]
        summary = PlanningAgent._build_source_summary(materials)
        assert "Test Doc" in summary
        assert "Source materials" in summary

    def test_research_agent_select_relevant_chunks(self):
        from agent.agents.research_agent import _select_relevant_chunks

        chunks = [
            {"text": "Python is a programming language", "index": 0},
            {"text": "Java is another language", "index": 1},
            {"text": "Python has great libraries for data science", "index": 2},
            {"text": "Weather forecast for tomorrow", "index": 3},
        ]
        chapter = {"title": "Python Basics", "key_concepts": ["Python", "programming"]}

        selected = _select_relevant_chunks(chapter, chunks, top_k=2)
        assert len(selected) == 2
        texts = [c["text"] for c in selected]
        assert any("Python" in t for t in texts)
        assert "Weather" not in " ".join(texts)
