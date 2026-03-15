"""
Tests for rubric_service — load, detect_overlay, and merge_rubric.

All tests are file-based: no real API or DB calls needed.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# Point the module at our real rubric fixtures
from api.services.rubric_service import (
    detect_overlay,
    load_rubric_json,
    merge_rubric,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def universal_base_path() -> Path:
    """Path to the real universal_base.json file."""
    return Path(__file__).resolve().parent.parent / "rubrics" / "universal_base.json"


@pytest.fixture
def streamlit_overlay_path() -> Path:
    return Path(__file__).resolve().parent.parent / "rubrics" / "overlay_streamlit_llm.json"


@pytest.fixture
def tmp_rubric(tmp_path: Path):
    """Factory for writing a rubric JSON to a temp file."""
    def _write(data: dict) -> Path:
        p = tmp_path / "test_rubric.json"
        p.write_text(json.dumps(data))
        return p
    return _write


# ---------------------------------------------------------------------------
# load_rubric_json
# ---------------------------------------------------------------------------


def test_load_rubric_json_real_file(universal_base_path):
    data = load_rubric_json(universal_base_path)
    assert data["type"] == "universal"
    assert len(data["dimensions"]) == 7


def test_load_rubric_json_returns_dict(universal_base_path):
    data = load_rubric_json(universal_base_path)
    assert isinstance(data, dict)
    assert "dimensions" in data


def test_load_rubric_json_missing_file():
    with pytest.raises(FileNotFoundError):
        load_rubric_json("/nonexistent/path/rubric.json")


def test_load_rubric_json_invalid_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json }")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_rubric_json(bad_file)


def test_load_rubric_json_all_dimensions_have_required_fields(universal_base_path):
    data = load_rubric_json(universal_base_path)
    for dim in data["dimensions"]:
        assert "id" in dim, f"Dimension missing 'id': {dim}"
        assert "name" in dim, f"Dimension missing 'name': {dim}"
        assert "description" in dim, f"Dimension missing 'description': {dim}"
        assert "category" in dim, f"Dimension missing 'category': {dim}"


# ---------------------------------------------------------------------------
# detect_overlay
# ---------------------------------------------------------------------------


def test_detect_overlay_streamlit():
    stack = {"frontend": "streamlit", "backend": "none", "llm_api": "anthropic"}
    result = detect_overlay(stack)
    assert result == "overlay_streamlit_llm.json"


def test_detect_overlay_gradio():
    stack = {"frontend": "gradio", "backend": "none", "llm_api": "openai"}
    result = detect_overlay(stack)
    assert result == "overlay_gradio_llm.json"


def test_detect_overlay_flask():
    stack = {"frontend": "react", "backend": "flask", "llm_api": "openai"}
    result = detect_overlay(stack)
    assert result == "overlay_flask_js_llm.json"


def test_detect_overlay_none_for_unknown_stack():
    stack = {"frontend": "svelte", "backend": "django", "llm_api": "none"}
    result = detect_overlay(stack)
    assert result is None


def test_detect_overlay_empty_dict():
    result = detect_overlay({})
    assert result is None


def test_detect_overlay_case_insensitive():
    stack = {"frontend": "Streamlit", "backend": "", "llm_api": ""}
    result = detect_overlay(stack)
    assert result == "overlay_streamlit_llm.json"


def test_detect_overlay_frontend_takes_precedence_over_backend():
    # Frontend is streamlit, backend is flask — streamlit should win
    stack = {"frontend": "streamlit", "backend": "flask", "llm_api": ""}
    result = detect_overlay(stack)
    assert result == "overlay_streamlit_llm.json"


# ---------------------------------------------------------------------------
# merge_rubric
# ---------------------------------------------------------------------------

BASE_DIMS = [
    {"id": "1", "name": "Code Quality", "sort_order": 1, "category": "code_quality"},
    {"id": "2", "name": "Error Handling", "sort_order": 2, "category": "error_handling"},
    {"id": "3", "name": "Architecture", "sort_order": 3, "category": "architecture"},
]

OVERLAY_DIMS_NEW = [
    {"id": "10", "name": "Streamlit State", "sort_order": 8, "category": "stack_specific"},
    {"id": "11", "name": "Claude Patterns", "sort_order": 9, "category": "stack_specific"},
]

OVERLAY_DIMS_DUPLICATE = [
    {"id": "99", "name": "Code Quality", "sort_order": 1, "category": "code_quality"},
    {"id": "10", "name": "Streamlit State", "sort_order": 8, "category": "stack_specific"},
]


def test_merge_rubric_combines_all_when_no_overlap():
    merged = merge_rubric(BASE_DIMS, OVERLAY_DIMS_NEW)
    assert len(merged) == 5


def test_merge_rubric_deduplicates_by_name():
    merged = merge_rubric(BASE_DIMS, OVERLAY_DIMS_DUPLICATE)
    # "Code Quality" should appear only once
    names = [d["name"] for d in merged]
    assert names.count("Code Quality") == 1
    assert len(merged) == 4


def test_merge_rubric_sorted_by_sort_order():
    merged = merge_rubric(BASE_DIMS, OVERLAY_DIMS_NEW)
    orders = [d["sort_order"] for d in merged]
    assert orders == sorted(orders)


def test_merge_rubric_base_wins_over_overlay():
    """Base dimension should survive deduplication, not the overlay version."""
    merged = merge_rubric(BASE_DIMS, OVERLAY_DIMS_DUPLICATE)
    cq = next(d for d in merged if d["name"] == "Code Quality")
    assert cq["id"] == "1"  # base id, not overlay's "99"


def test_merge_rubric_empty_overlay():
    merged = merge_rubric(BASE_DIMS, [])
    assert len(merged) == len(BASE_DIMS)


def test_merge_rubric_empty_base():
    merged = merge_rubric([], OVERLAY_DIMS_NEW)
    assert len(merged) == len(OVERLAY_DIMS_NEW)


def test_merge_rubric_both_empty():
    merged = merge_rubric([], [])
    assert merged == []


def test_merge_real_rubric_files(universal_base_path, streamlit_overlay_path):
    """Integration test: merge actual JSON files from the rubrics directory."""
    base_data = load_rubric_json(universal_base_path)
    overlay_data = load_rubric_json(streamlit_overlay_path)

    merged = merge_rubric(base_data["dimensions"], overlay_data["dimensions"])

    # Should have 7 base + 2 overlay = 9 total
    assert len(merged) == 9

    # All should be sorted
    orders = [d.get("sort_order", 0) for d in merged]
    assert orders == sorted(orders)

    # Overlay dimensions present
    names = [d["name"] for d in merged]
    assert "Streamlit State Management" in names
    assert "Claude Integration Patterns" in names
