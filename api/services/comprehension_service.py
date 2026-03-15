"""
Comprehension service.

Tracks whether students acted on feedback by correlating post-review
commits with the files mentioned in feedback action items.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from supabase import Client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------


def match_commit_to_feedback(
    files_changed: list[str],
    review_id: str,
    client: Optional[Client] = None,
) -> bool:
    """
    Determine whether a commit's changed files overlap with files mentioned
    in the feedback for a review.

    Strategy:
    - Fetch all red/yellow action_items for the review.
    - Extract file-like tokens from action items using a simple regex.
    - Check if any changed file matches a mentioned file.

    Returns True if at least one changed file is mentioned in feedback.
    Falls back to True if no client is provided (non-DB mode for testing).
    """
    if client is None:
        # Simple heuristic when no DB: any .py file change counts
        return any(f.endswith(".py") for f in files_changed)

    try:
        scores_resp = (
            client.table("review_scores")
            .select("action_item, score")
            .eq("review_id", review_id)
            .in_("score", ["red", "yellow"])
            .execute()
        )
        rows = scores_resp.data or []
        mentioned_files: set[str] = set()
        for row in rows:
            action = row.get("action_item") or ""
            # Extract tokens that look like file paths (contain / or .)
            tokens = re.findall(r"[\w./\-]+\.[\w]+", action)
            for t in tokens:
                mentioned_files.add(t.lower())

        if not mentioned_files:
            # No specific files mentioned → treat any code change as addressing it
            return bool(files_changed)

        for f in files_changed:
            base = f.split("/")[-1].lower()  # check filename only
            if base in mentioned_files or f.lower() in mentioned_files:
                return True

        return False

    except Exception as exc:
        logger.error("match_commit_to_feedback error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log_comprehension_event(
    client: Client,
    review_id: str,
    commit_sha: str,
    commit_timestamp: datetime,
    files_changed: list[str],
    addressed: bool,
    hours_after: Optional[float] = None,
    review_score_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Persist a ComprehensionEvent row to track whether a student acted on
    specific feedback after delivery.
    """
    try:
        payload = {
            "review_id": review_id,
            "commit_sha": commit_sha,
            "commit_timestamp": commit_timestamp.isoformat(),
            "files_changed": files_changed,
            "addressed": addressed,
            "hours_after_delivery": hours_after,
        }
        if review_score_id:
            payload["review_score_id"] = review_score_id

        resp = client.table("comprehension_events").insert(payload).execute()
        data = resp.data
        if isinstance(data, list):
            data = data[0] if data else None
        return data

    except Exception as exc:
        logger.error("log_comprehension_event error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Rate calculation
# ---------------------------------------------------------------------------


def calculate_comprehension_rate(
    client: Client,
    ta_id: str,
) -> float:
    """
    Calculate the percentage of this TA's red/yellow feedback items that
    the student subsequently addressed (based on comprehension_events).

    Returns a float 0.0–100.0.
    """
    try:
        # Get all delivered reviews for this TA
        reviews_resp = (
            client.table("reviews")
            .select("id")
            .eq("ta_id", ta_id)
            .in_("status", ["submitted", "delivered"])
            .execute()
        )
        review_ids = [r["id"] for r in (reviews_resp.data or [])]
        if not review_ids:
            return 0.0

        # Get all comprehension events for those reviews
        events_resp = (
            client.table("comprehension_events")
            .select("addressed")
            .in_("review_id", review_ids)
            .execute()
        )
        events = events_resp.data or []
        if not events:
            return 0.0

        addressed_count = sum(1 for e in events if e.get("addressed"))
        return round(addressed_count / len(events) * 100, 1)

    except Exception as exc:
        logger.error("calculate_comprehension_rate error: %s", exc)
        return 0.0
