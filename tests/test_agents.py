"""Basic unit tests for agent state transformations."""
import pytest


BASE_STATE = {
    "title": "Test Book",
    "description": "A test book",
    "language": "English",
    "words_per_chapter": "500-1000",
    "num_chapters": 2,
    "writing_guidelines": [],
    "core_themes": ["testing"],
    "target_audience": "Developers",
    "tone": "Technical",
    "planned_chapters": [
        {
            "number": 1,
            "title": "Introduction",
            "purpose": "Introduce the topic",
            "key_concepts": ["basics", "overview"],
            "learning_objectives": ["Understand fundamentals"],
        }
    ],
    "current_chapter": {
        "number": 1,
        "title": "Introduction",
        "description": "An introduction chapter",
    },
    "completed_chapters": [],
    "errors": [],
}


def test_evaluator_threshold():
    """Verify evaluator constants are set correctly."""
    from agent.agents.evaluator_agent import REWRITE_THRESHOLD, REVISION_THRESHOLD
    assert REWRITE_THRESHOLD < REVISION_THRESHOLD
    assert REWRITE_THRESHOLD == 55.0
    assert REVISION_THRESHOLD == 70.0


def test_state_has_required_fields():
    """Verify base state has all required fields for workflow."""
    required = ["title", "description", "language", "words_per_chapter", "num_chapters"]
    for field in required:
        assert field in BASE_STATE, f"Missing required field: {field}"


def test_chapter_workflow_max_rewrites():
    """Verify MAX_REWRITES constant is defined."""
    from agent.workflows.chapter_workflow import MAX_REWRITES
    assert MAX_REWRITES >= 1
    assert MAX_REWRITES <= 5


def test_output_manager_creates_dir(tmp_path):
    """OutputManager should create the output directory."""
    from agent.workflows.output_manager import OutputManager
    om = OutputManager(str(tmp_path), "Test Book")
    assert (tmp_path / "test-book").exists()


def test_output_manager_save_and_load_progress(tmp_path):
    """Progress should round-trip correctly."""
    from agent.workflows.output_manager import OutputManager
    om = OutputManager(str(tmp_path), "Test Book")
    progress = {"completed": [1, 2], "failed": {}, "in_progress": None}
    om.save_progress(progress)
    loaded = om.load_progress()
    assert loaded["completed"] == [1, 2]


def test_output_manager_save_chapter(tmp_path):
    """Chapter markdown file should be created with front matter."""
    from agent.workflows.output_manager import OutputManager
    om = OutputManager(str(tmp_path), "Test Book")
    chapter_data = {
        "number": 1,
        "title": "Introduction",
        "content": "# Introduction\n\nThis is the first chapter.",
        "word_count": 7,
        "evaluation_score": 82.5,
        "rewrite_count": 0,
        "evaluation": {},
    }
    filepath = om.save_chapter(chapter_data)
    assert filepath.exists()
    content = filepath.read_text(encoding="utf-8")
    assert "chapter: 1" in content
    assert "quality_score: 82.5" in content
    assert "Introduction\n\nThis is the first chapter." in content
