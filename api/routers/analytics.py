"""
Analytics router.

Instructor-level aggregate cohort metrics and per-TA impact metrics.
"""

from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from api.models.database import get_supabase_client, handle_response
from api.services.comprehension_service import calculate_comprehension_rate

router = APIRouter()


def db() -> Client:
    return get_supabase_client()


@router.get("/instructor")
def instructor_analytics(
    client: Client = Depends(db),
) -> dict:
    """
    Aggregate metrics across the entire cohort.

    Returns:
    - comprehension_rate: % of red/yellow items addressed by students
    - ta_adoption_rate: % of TAs who have submitted at least one review
    - rubric_consistency: average score agreement across TAs per dimension
    - dimensions_needing_attention: dimensions with highest red/yellow rate
    - top_issues: most common action items / comments
    """
    try:
        # --- TA adoption ---
        ta_resp = (
            client.table("users")
            .select("id")
            .eq("role", "ta")
            .execute()
        )
        all_tas = ta_resp.data or []
        ta_ids = {row["id"] for row in all_tas}

        active_ta_resp = (
            client.table("reviews")
            .select("ta_id")
            .in_("status", ["submitted", "delivered"])
            .execute()
        )
        active_tas = {row["ta_id"] for row in (active_ta_resp.data or [])}
        ta_adoption_rate = (
            round(len(active_tas) / len(ta_ids) * 100, 1) if ta_ids else 0.0
        )

        # --- Score distribution for rubric consistency ---
        scores_resp = (
            client.table("review_scores")
            .select(
                "score, dimension_id, "
                "review:reviews!inner(ta_id, status)"
            )
            .in_("review.status", ["submitted", "delivered"])
            .execute()
        )
        score_rows = scores_resp.data or []

        # Consistency: per dimension, if >80% of scores agree → consistent
        dim_scores: dict[str, list] = defaultdict(list)
        for row in score_rows:
            dim_scores[row["dimension_id"]].append(row["score"])

        consistency_scores = []
        for scores_list in dim_scores.values():
            if not scores_list:
                continue
            most_common = max(set(scores_list), key=scores_list.count)
            pct = scores_list.count(most_common) / len(scores_list)
            consistency_scores.append(pct)

        rubric_consistency = (
            round(sum(consistency_scores) / len(consistency_scores) * 100, 1)
            if consistency_scores
            else 0.0
        )

        # --- Dimensions needing attention ---
        dim_red_yellow: dict[str, dict] = defaultdict(lambda: {"total": 0, "bad": 0, "name": ""})
        dim_name_resp = (
            client.table("rubric_dimensions").select("id, name").execute()
        )
        dim_names = {row["id"]: row["name"] for row in (dim_name_resp.data or [])}

        for row in score_rows:
            d = row["dimension_id"]
            dim_red_yellow[d]["total"] += 1
            dim_red_yellow[d]["name"] = dim_names.get(d, d)
            if row["score"] in ("red", "yellow"):
                dim_red_yellow[d]["bad"] += 1

        attention_dims = [
            {
                "dimension_id": d,
                "name": info["name"],
                "red_yellow_rate": round(info["bad"] / info["total"] * 100, 1),
            }
            for d, info in dim_red_yellow.items()
            if info["total"] > 0
        ]
        attention_dims.sort(key=lambda x: x["red_yellow_rate"], reverse=True)

        # --- Top issues (most common action items) ---
        action_resp = (
            client.table("review_scores")
            .select("action_item")
            .not_.is_("action_item", "null")
            .execute()
        )
        action_counts: dict[str, int] = defaultdict(int)
        for row in (action_resp.data or []):
            item = (row.get("action_item") or "").strip()
            if item:
                action_counts[item] += 1
        top_issues = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]

        # --- Comprehension rate (cohort-wide) ---
        comp_resp = (
            client.table("comprehension_events")
            .select("addressed")
            .execute()
        )
        comp_rows = comp_resp.data or []
        total_comp = len(comp_rows)
        addressed = sum(1 for r in comp_rows if r.get("addressed"))
        comprehension_rate = (
            round(addressed / total_comp * 100, 1) if total_comp else 0.0
        )

        return {
            "comprehension_rate": comprehension_rate,
            "ta_adoption_rate": ta_adoption_rate,
            "rubric_consistency": rubric_consistency,
            "dimensions_needing_attention": attention_dims[:5],
            "top_issues": [{"action_item": k, "count": v} for k, v in top_issues],
            "total_reviews": len(score_rows),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ta/{ta_id}")
def ta_analytics(
    ta_id: UUID,
    client: Client = Depends(db),
) -> dict:
    """
    Personal impact metrics for a single TA.

    Returns:
    - reviews_submitted: total reviews submitted by this TA
    - comprehension_rate: % of this TA's red/yellow feedback acted on
    - cohort_comprehension_rate: cohort average for comparison
    - score_distribution: breakdown of scores this TA has given
    - most_impactful_items: action items most often acted on
    """
    try:
        # Reviews submitted
        rev_resp = (
            client.table("reviews")
            .select("id")
            .eq("ta_id", str(ta_id))
            .in_("status", ["submitted", "delivered"])
            .execute()
        )
        review_ids = [r["id"] for r in (rev_resp.data or [])]

        # Score distribution
        if review_ids:
            scores_resp = (
                client.table("review_scores")
                .select("score, action_item")
                .in_("review_id", review_ids)
                .execute()
            )
            score_rows = scores_resp.data or []
        else:
            score_rows = []

        dist: dict[str, int] = defaultdict(int)
        for row in score_rows:
            dist[row["score"]] += 1

        # Comprehension rate for this TA
        ta_comp_rate = await_safe(calculate_comprehension_rate, client, str(ta_id))

        # Cohort comprehension rate
        all_comp_resp = (
            client.table("comprehension_events")
            .select("addressed")
            .execute()
        )
        all_comp = all_comp_resp.data or []
        cohort_rate = (
            round(sum(1 for r in all_comp if r.get("addressed")) / len(all_comp) * 100, 1)
            if all_comp
            else 0.0
        )

        # Most impactful items (acted on)
        impactful_resp = (
            client.table("comprehension_events")
            .select("review_score_id, addressed")
            .eq("addressed", True)
            .execute()
        )
        acted_score_ids = [
            r["review_score_id"] for r in (impactful_resp.data or []) if r.get("review_score_id")
        ]
        impactful_items = []
        if acted_score_ids and review_ids:
            imp_scores_resp = (
                client.table("review_scores")
                .select("action_item, dimension_id")
                .in_("id", acted_score_ids)
                .in_("review_id", review_ids)
                .not_.is_("action_item", "null")
                .execute()
            )
            item_counts: dict[str, int] = defaultdict(int)
            for row in (imp_scores_resp.data or []):
                item = (row.get("action_item") or "").strip()
                if item:
                    item_counts[item] += 1
            impactful_items = sorted(
                [{"action_item": k, "count": v} for k, v in item_counts.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:5]

        return {
            "ta_id": str(ta_id),
            "reviews_submitted": len(review_ids),
            "comprehension_rate": ta_comp_rate,
            "cohort_comprehension_rate": cohort_rate,
            "score_distribution": dict(dist),
            "most_impactful_items": impactful_items,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def await_safe(sync_fn, *args, **kwargs):
    """Call a synchronous function, returning 0.0 on any error."""
    try:
        return sync_fn(*args, **kwargs)
    except Exception:
        return 0.0
