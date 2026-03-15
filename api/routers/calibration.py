"""
Calibration router.

Provides TA calibration views: anonymized score distributions across
all TAs for an assignment, and individual "my scores vs peers" comparison.
"""

from collections import defaultdict
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.models.database import get_supabase_client, handle_response

router = APIRouter()


def db() -> Client:
    return get_supabase_client()


@router.get("/{assignment_id}")
def get_calibration(
    assignment_id: UUID,
    client: Client = Depends(db),
) -> dict:
    """
    Return anonymized score distributions and common feedback themes for
    all TAs who have reviewed this assignment.

    Shape:
    {
      "dimensions": [
        {
          "dimension_id": "...",
          "name": "Code Quality",
          "distribution": {"green": 5, "yellow": 3, "red": 2},
          "themes": ["Missing error handling", ...]
        },
        ...
      ],
      "total_reviews": 10
    }
    """
    try:
        # Fetch all submitted/delivered review scores for this assignment
        resp = (
            client.table("review_scores")
            .select(
                "score, comment, action_item, "
                "dimension:rubric_dimensions(id, name, category), "
                "review:reviews!inner(status, submission:submissions!inner(assignment_id))"
            )
            .eq("review.submission.assignment_id", str(assignment_id))
            .in_("review.status", ["submitted", "delivered"])
            .execute()
        )
        rows = resp.data or []

        # Aggregate
        dim_map: dict[str, dict] = {}
        total_review_ids: set = set()

        for row in rows:
            dim = row.get("dimension") or {}
            dim_id = dim.get("id", "unknown")
            dim_name = dim.get("name", "Unknown")
            score = row.get("score", "")
            comment = row.get("comment") or ""

            if dim_id not in dim_map:
                dim_map[dim_id] = {
                    "dimension_id": dim_id,
                    "name": dim_name,
                    "distribution": defaultdict(int),
                    "comments": [],
                }

            dim_map[dim_id]["distribution"][score] += 1
            if comment:
                dim_map[dim_id]["comments"].append(comment)

        # Build response, convert defaultdict → plain dict
        dimensions = []
        for info in dim_map.values():
            # Simple theme extraction: take up to 5 unique non-empty comments
            themes = list(dict.fromkeys(info["comments"]))[:5]
            dimensions.append(
                {
                    "dimension_id": info["dimension_id"],
                    "name": info["name"],
                    "distribution": dict(info["distribution"]),
                    "themes": themes,
                }
            )

        # Sort by dimension name
        dimensions.sort(key=lambda d: d["name"])

        return {
            "dimensions": dimensions,
            "total_reviews": len(rows),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{assignment_id}/my-vs-peers")
def my_vs_peers(
    assignment_id: UUID,
    ta_id: UUID = Query(..., description="TA whose scores to compare against cohort"),
    client: Client = Depends(db),
) -> dict:
    """
    Compare a TA's score distribution against the cohort average per dimension.

    Shape:
    {
      "ta_id": "...",
      "dimensions": [
        {
          "dimension_id": "...",
          "name": "...",
          "my_distribution": {"green": 3, "yellow": 1, "red": 0},
          "cohort_distribution": {"green": 4.2, "yellow": 1.8, "red": 0.5},
        }
      ]
    }
    """
    try:
        resp = (
            client.table("review_scores")
            .select(
                "score, "
                "dimension:rubric_dimensions(id, name), "
                "review:reviews!inner(ta_id, status, submission:submissions!inner(assignment_id))"
            )
            .eq("review.submission.assignment_id", str(assignment_id))
            .in_("review.status", ["submitted", "delivered"])
            .execute()
        )
        rows = resp.data or []

        # Separate my scores vs all
        my_dims: dict[str, dict] = {}
        all_dims: dict[str, dict] = {}

        for row in rows:
            dim = row.get("dimension") or {}
            dim_id = dim.get("id", "unknown")
            dim_name = dim.get("name", "Unknown")
            score = row.get("score", "")
            review = row.get("review") or {}
            is_mine = str(review.get("ta_id", "")) == str(ta_id)

            for store, flag in [(all_dims, True), (my_dims, is_mine)]:
                if not flag:
                    continue
                if dim_id not in store:
                    store[dim_id] = {
                        "dimension_id": dim_id,
                        "name": dim_name,
                        "distribution": defaultdict(int),
                        "count": 0,
                    }
                store[dim_id]["distribution"][score] += 1
                store[dim_id]["count"] += 1

        # Build per-dimension comparison
        score_keys = ["green", "yellow", "red", "not_applicable", "flagged_for_help"]
        dimensions = []
        for dim_id, all_info in all_dims.items():
            my_info = my_dims.get(dim_id, {"distribution": {}, "count": 0})
            total_all = all_info["count"] or 1

            cohort_avg = {
                k: round(all_info["distribution"].get(k, 0) / total_all, 2)
                for k in score_keys
            }
            dimensions.append(
                {
                    "dimension_id": dim_id,
                    "name": all_info["name"],
                    "my_distribution": dict(my_info["distribution"]),
                    "cohort_distribution": cohort_avg,
                }
            )

        dimensions.sort(key=lambda d: d["name"])
        return {"ta_id": str(ta_id), "dimensions": dimensions}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
