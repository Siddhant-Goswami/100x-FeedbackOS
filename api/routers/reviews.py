"""
Reviews router.

Core review lifecycle: create, score, suggest actions, flag for help,
submit.  Also exposes the merged rubric for a given assignment.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.models.database import get_supabase_client, handle_response
from api.models.schemas import (
    CreateReviewRequest,
    FlagForHelpRequest,
    Review,
    ReviewScore,
    RubricDimension,
    ScoreRequest,
    SuggestActionRequest,
    UpdateReviewRequest,
)
from api.services import llm_service, review_service, rubric_service  # rubric_service used in submit
from api.services.notification_service import send_feedback_notification

router = APIRouter()


def db() -> Client:
    return get_supabase_client()


# ---------------------------------------------------------------------------
# Review CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=Review)
def create_review(
    body: CreateReviewRequest,
    client: Client = Depends(db),
) -> Review:
    """Create a draft review (idempotent — returns existing draft if present)."""
    try:
        return review_service.create_review(
            client, str(body.submission_id), str(body.ta_id)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{review_id}", response_model=Review)
def update_review(
    review_id: UUID,
    body: UpdateReviewRequest,
    client: Client = Depends(db),
) -> Review:
    """Update top-level review metadata (overall comment, status)."""
    try:
        payload = body.model_dump(exclude_none=True)
        if not payload:
            raise HTTPException(status_code=400, detail="No fields to update.")

        resp = (
            client.table("reviews")
            .update(payload)
            .eq("id", str(review_id))
            .execute()
        )
        data = handle_response(resp)
        if isinstance(data, list):
            data = data[0]
        return Review(**data)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


@router.get("/{review_id}/scores", response_model=list[ReviewScore])
def get_scores(
    review_id: UUID,
    client: Client = Depends(db),
) -> list[ReviewScore]:
    """Return all scores for a review, joined with dimension info."""
    try:
        resp = (
            client.table("review_scores")
            .select("*, dimension:rubric_dimensions(*)")
            .eq("review_id", str(review_id))
            .execute()
        )
        data = handle_response(resp)
        return [ReviewScore(**row) for row in data]

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{review_id}/scores", response_model=ReviewScore)
def upsert_score(
    review_id: UUID,
    body: ScoreRequest,
    client: Client = Depends(db),
) -> ReviewScore:
    """Upsert a single dimension score for a review."""
    try:
        return review_service.upsert_score(
            client,
            review_id=str(review_id),
            dimension_id=str(body.dimension_id),
            score=body.score.value,
            comment=body.comment,
            action_item=body.action_item,
            source=body.action_item_source.value if body.action_item_source else None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# AI assistance
# ---------------------------------------------------------------------------


@router.post("/{review_id}/suggest-action")
async def suggest_action(
    review_id: UUID,
    body: SuggestActionRequest,
    client: Client = Depends(db),
) -> dict:
    """
    Request an AI-generated action item suggestion for a dimension score.
    Returns {suggested_action_item, reasoning}.
    """
    try:
        # Fetch dimension details
        dim_resp = (
            client.table("rubric_dimensions")
            .select("*")
            .eq("id", str(body.dimension_id))
            .single()
            .execute()
        )
        dim_data = handle_response(dim_resp)
        dim = RubricDimension(**dim_data)

        # Fetch existing examples for this dimension
        ex_resp = (
            client.table("example_feedback")
            .select("*")
            .eq("dimension_id", str(body.dimension_id))
            .limit(3)
            .execute()
        )
        examples = ex_resp.data or []

        result = await llm_service.suggest_action_item(
            dimension_name=dim.name,
            dimension_desc=dim.description,
            score=body.score.value,
            code_snippet=body.code_snippet or "",
            examples=examples,
        )
        return result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Flag for help
# ---------------------------------------------------------------------------


@router.post("/{review_id}/flag-for-help")
def flag_for_help(
    review_id: UUID,
    body: FlagForHelpRequest,
    client: Client = Depends(db),
) -> dict:
    """
    Mark a specific dimension as 'flagged for help' so a senior TA or
    instructor can weigh in before the review is delivered.
    """
    try:
        # Upsert a review_score row with flagged status
        payload = {
            "review_id": str(review_id),
            "dimension_id": str(body.dimension_id),
            "score": "flagged_for_help",
            "is_flagged_for_help": True,
            "flag_note": body.note,
        }
        resp = (
            client.table("review_scores")
            .upsert(payload, on_conflict="review_id,dimension_id")
            .execute()
        )
        handle_response(resp)

        # Also flag the parent submission for visibility
        # (best-effort — don't fail the whole request if this errors)
        try:
            sub_resp = (
                client.table("reviews")
                .select("submission_id")
                .eq("id", str(review_id))
                .single()
                .execute()
            )
            if sub_resp.data:
                client.table("submissions").update(
                    {"is_flagged": True, "flag_note": body.note}
                ).eq("id", sub_resp.data["submission_id"]).execute()
        except Exception:
            pass

        return {"status": "flagged", "review_id": str(review_id)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


@router.post("/{review_id}/submit")
async def submit_review(
    review_id: UUID,
    client: Client = Depends(db),
) -> dict:
    """
    Submit a completed review.

    Validates that all required dimensions have been scored, marks the
    review as submitted, updates the submission status, and sends a
    Discord notification to the student.
    """
    try:
        # 1. Fetch review + submission
        rev_resp = (
            client.table("reviews")
            .select("*, submission:submissions(*, student:users!submissions_student_id_fkey(*), assignment:assignments(*))")
            .eq("id", str(review_id))
            .single()
            .execute()
        )
        review_data = handle_response(rev_resp)
        review = Review(**review_data)

        if review.status.value != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Review is already in '{review.status.value}' state.",
            )

        # 2. Fetch rubric dimensions for this assignment
        assignment_id = review_data["submission"]["assignment_id"]
        dims = rubric_service.get_rubric_for_assignment(client, assignment_id)

        # 3. Completeness check
        incomplete = review_service.check_completeness(client, str(review_id), dims)
        if incomplete:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Review is incomplete. Please score all required dimensions.",
                    "unscored": incomplete,
                },
            )

        # 4. Mark as submitted
        review_service.submit_review(client, str(review_id))

        # 5. Notify student via Discord (best-effort)
        student = review_data["submission"].get("student", {})
        discord_id = student.get("discord_id")
        if discord_id:
            try:
                assignment_title = review_data["submission"]["assignment"].get(
                    "title", "your project"
                )
                feedback_url = f"/feedback?review_id={review_id}"
                await send_feedback_notification(
                    student_discord_id=discord_id,
                    review_id=str(review_id),
                    student_name=student.get("name", ""),
                    project_title=assignment_title,
                    feedback_url=feedback_url,
                )
            except Exception as notify_exc:
                # Notification failure should not block review submission
                import logging
                logging.getLogger(__name__).warning(
                    "Discord notification failed: %s", notify_exc
                )

        return {"status": "submitted", "review_id": str(review_id)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


