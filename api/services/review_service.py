"""
Review service.

Business logic for the review lifecycle: create, score, validate,
and submit reviews.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from supabase import Client

from api.models.schemas import Review, ReviewScore, RubricDimension

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_review(
    client: Client,
    submission_id: str,
    ta_id: str,
) -> Review:
    """
    Create a draft review for a submission.

    Idempotent — if a draft review already exists for this
    (submission_id, ta_id) pair, return it unchanged.
    """
    try:
        # Check for existing draft
        existing_resp = (
            client.table("reviews")
            .select("*")
            .eq("submission_id", submission_id)
            .eq("ta_id", ta_id)
            .eq("status", "draft")
            .maybe_single()
            .execute()
        )
        if existing_resp.data:
            return Review(**existing_resp.data)

        # Create new draft
        payload = {
            "submission_id": submission_id,
            "ta_id": ta_id,
            "status": "draft",
        }
        insert_resp = client.table("reviews").insert(payload).execute()
        if not insert_resp.data:
            raise HTTPException(
                status_code=500, detail="Failed to create review record."
            )
        data = insert_resp.data
        if isinstance(data, list):
            data = data[0]

        # Update submission status to under_review
        client.table("submissions").update({"status": "under_review"}).eq(
            "id", submission_id
        ).execute()

        return Review(**data)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_review error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Upsert score
# ---------------------------------------------------------------------------


def upsert_score(
    client: Client,
    review_id: str,
    dimension_id: str,
    score: str,
    comment: Optional[str] = None,
    action_item: Optional[str] = None,
    source: Optional[str] = None,
) -> ReviewScore:
    """
    Create or update a review score for a specific dimension.

    Uses upsert on (review_id, dimension_id) to ensure at most one
    score per dimension per review.
    """
    try:
        payload: dict = {
            "review_id": review_id,
            "dimension_id": dimension_id,
            "score": score,
            "is_flagged_for_help": score == "flagged_for_help",
        }
        if comment is not None:
            payload["comment"] = comment
        if action_item is not None:
            payload["action_item"] = action_item
        if source is not None:
            payload["action_item_source"] = source

        resp = (
            client.table("review_scores")
            .upsert(payload, on_conflict="review_id,dimension_id")
            .execute()
        )
        data = resp.data
        if not data:
            raise HTTPException(status_code=500, detail="Failed to upsert score.")
        if isinstance(data, list):
            data = data[0]
        return ReviewScore(**data)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("upsert_score error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Completeness check
# ---------------------------------------------------------------------------


def check_completeness(
    client: Client,
    review_id: str,
    rubric_dimensions: list[RubricDimension],
) -> list[str]:
    """
    Return names of required dimensions that have NOT been scored.

    An empty list means the review is complete.
    """
    try:
        scored_resp = (
            client.table("review_scores")
            .select("dimension_id, score")
            .eq("review_id", review_id)
            .execute()
        )
        scored_ids = {
            row["dimension_id"]
            for row in (scored_resp.data or [])
            if row.get("score") not in (None, "", "flagged_for_help")
        }

        unscored = [
            dim.name
            for dim in rubric_dimensions
            if dim.is_required and str(dim.id) not in scored_ids
        ]
        return unscored

    except Exception as exc:
        logger.error("check_completeness error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


def submit_review(
    client: Client,
    review_id: str,
) -> None:
    """
    Mark a review as submitted and record the submitted_at timestamp.
    Also updates the parent submission to 'reviewed' status.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_resp = (
            client.table("reviews")
            .update({"status": "submitted", "submitted_at": now})
            .eq("id", review_id)
            .execute()
        )
        if not update_resp.data:
            raise HTTPException(
                status_code=500, detail="Failed to update review status."
            )

        data = update_resp.data
        if isinstance(data, list):
            data = data[0]
        submission_id = data.get("submission_id")

        if submission_id:
            client.table("submissions").update({"status": "reviewed"}).eq(
                "id", submission_id
            ).execute()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("submit_review error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
