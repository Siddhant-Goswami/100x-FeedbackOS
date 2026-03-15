"""
Rubric service.

Loads rubric definitions from JSON files and from Supabase, and merges
base rubrics with stack-specific overlays.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from supabase import Client

from api.config import RUBRIC_DIR
from api.models.schemas import RubricDimension

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stack → overlay file mapping
# ---------------------------------------------------------------------------

_OVERLAY_MAP: dict[str, str] = {
    "streamlit": "overlay_streamlit_llm.json",
    "gradio": "overlay_gradio_llm.json",
    "flask": "overlay_flask_js_llm.json",
}


# ---------------------------------------------------------------------------
# File-based helpers
# ---------------------------------------------------------------------------


def load_rubric_json(filepath: Path | str) -> dict:
    """
    Load and parse a rubric JSON file.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the JSON is malformed.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Rubric file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in rubric file {path}: {exc}") from exc


def detect_overlay(detected_stack: dict) -> Optional[str]:
    """
    Given a detected_stack dict (keys: frontend, backend, llm_api, ...),
    return the overlay filename that matches, or None.

    Precedence: frontend > backend > llm_api
    """
    for key in ("frontend", "backend", "llm_api"):
        value = (detected_stack.get(key) or "").lower()
        for stack_keyword, overlay_file in _OVERLAY_MAP.items():
            if stack_keyword in value:
                return overlay_file
    return None


def merge_rubric(
    base_dimensions: list[dict],
    overlay_dimensions: list[dict],
) -> list[dict]:
    """
    Merge base + overlay dimension lists.

    - Overlay dimensions with names that match an existing base dimension
      are skipped (base takes precedence).
    - Otherwise overlay dimensions are appended.
    - Final list is sorted by sort_order then name.
    """
    base_names = {d.get("name", "").lower() for d in base_dimensions}

    merged = list(base_dimensions)
    for dim in overlay_dimensions:
        if dim.get("name", "").lower() not in base_names:
            merged.append(dim)

    merged.sort(key=lambda d: (d.get("sort_order", 99), d.get("name", "")))
    return merged


# ---------------------------------------------------------------------------
# DB-based helpers
# ---------------------------------------------------------------------------


def get_rubric_for_assignment(
    client: Client,
    assignment_id: str,
) -> list[RubricDimension]:
    """
    Fetch the rubric dimensions for an assignment from Supabase.

    Strategy:
    1. Look up the assignment's rubric_id.
    2. Fetch all dimensions for that rubric (universal base).
    3. Detect overlay from submission's detected_stack (if any).
    4. Fetch overlay dimensions and merge.

    Returns sorted list of RubricDimension objects.
    """
    try:
        # 1. Assignment → rubric_id
        assign_resp = (
            client.table("assignments")
            .select("id, rubric_id")
            .eq("id", assignment_id)
            .single()
            .execute()
        )
        if not assign_resp.data:
            raise HTTPException(
                status_code=404,
                detail=f"Assignment {assignment_id} not found.",
            )
        rubric_id: Optional[str] = assign_resp.data.get("rubric_id")

        # 2. Base dimensions
        base_dims_raw: list[dict] = []
        if rubric_id:
            dims_resp = (
                client.table("rubric_dimensions")
                .select("*")
                .eq("rubric_id", rubric_id)
                .order("sort_order")
                .execute()
            )
            base_dims_raw = dims_resp.data or []

        # 3. Detect overlay from a recent submission's detected stack
        detected_stack: dict = {}
        sub_resp = (
            client.table("submissions")
            .select("id")
            .eq("assignment_id", assignment_id)
            .limit(1)
            .execute()
        )
        if sub_resp.data:
            first_sub_id = sub_resp.data[0]["id"]
            stack_resp = (
                client.table("detected_stacks")
                .select("frontend, backend, llm_api")
                .eq("submission_id", first_sub_id)
                .maybe_single()
                .execute()
            )
            detected_stack = stack_resp.data or {}
        overlay_file = detect_overlay(detected_stack)

        # 4. Overlay dimensions
        overlay_dims_raw: list[dict] = []
        if overlay_file:
            # Try loading from file first (seeded rubrics may not be in DB yet)
            overlay_path = RUBRIC_DIR / overlay_file
            try:
                overlay_data = load_rubric_json(overlay_path)
                overlay_dims_raw = overlay_data.get("dimensions", [])
            except (FileNotFoundError, ValueError) as exc:
                logger.warning("Could not load overlay %s: %s", overlay_file, exc)

        # 5. Merge and return
        merged = merge_rubric(base_dims_raw, overlay_dims_raw)
        return [RubricDimension(**d) for d in merged if "id" in d]

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_rubric_for_assignment error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
