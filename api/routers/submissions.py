"""
Submissions router.

Handles listing/fetching student project submissions and triggering
automated stack detection.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.models.database import get_supabase_client, handle_response
from api.models.schemas import Submission, SubmissionListResponse
from api.services import llm_service, github_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def db() -> Client:
    return get_supabase_client()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=SubmissionListResponse)
def list_submissions(
    ta_id: Optional[UUID] = Query(None, description="Filter by assigned TA"),
    status: Optional[str] = Query(None, description="Filter by submission status"),
    assignment_id: Optional[UUID] = Query(None, description="Filter by assignment"),
    client: Client = Depends(db),
) -> SubmissionListResponse:
    """
    Return a paginated list of submissions, optionally filtered by TA,
    status, or assignment.  Flagged submissions are sorted to the top by
    the frontend; we return a stable order by created_at DESC here.
    """
    try:
        query = client.table("submissions").select(
            "*, student:users!submissions_student_id_fkey(*), "
            "assignment:assignments(*), detected_stack:detected_stacks(*)"
        )

        if ta_id:
            query = query.eq("ta_id", str(ta_id))
        if status:
            query = query.eq("status", status)
        if assignment_id:
            query = query.eq("assignment_id", str(assignment_id))

        query = query.order("created_at", desc=True)
        response = query.execute()
        data = handle_response(response)

        submissions = [Submission(**row) for row in data]
        return SubmissionListResponse(items=submissions, total=len(submissions))

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{submission_id}", response_model=Submission)
def get_submission(
    submission_id: UUID,
    client: Client = Depends(db),
) -> Submission:
    """
    Return a single submission with files and detected stack included.
    """
    try:
        response = (
            client.table("submissions")
            .select(
                "*, "
                "student:users!submissions_student_id_fkey(*), "
                "assignment:assignments(*), "
                "files:submission_files(*), "
                "detected_stack:detected_stacks(*)"
            )
            .eq("id", str(submission_id))
            .single()
            .execute()
        )
        data = handle_response(response)
        return Submission(**data)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{submission_id}/detect-stack")
async def detect_stack(
    submission_id: UUID,
    client: Client = Depends(db),
) -> dict:
    """
    Trigger stack detection for a submission.

    1. Fetch submission + repo URL from DB.
    2. Pull file tree + key file snippets from GitHub.
    3. Call LLM service to classify the stack.
    4. Upsert the result into detected_stacks table.
    """
    try:
        # 1. Fetch submission
        sub_resp = (
            client.table("submissions")
            .select("id, github_repo_url, commit_sha")
            .eq("id", str(submission_id))
            .single()
            .execute()
        )
        sub = handle_response(sub_resp)
        repo_url: str = sub["github_repo_url"]
        commit_sha: Optional[str] = sub.get("commit_sha")

        # 2. Gather repo data
        file_tree = await github_service.fetch_repo_files(repo_url, commit_sha)
        key_snippets = await github_service.parse_key_files(repo_url)

        # 3. Detect stack via LLM
        detected = await llm_service.detect_stack(file_tree, key_snippets)

        # 4. Upsert result
        payload = {
            "submission_id": str(submission_id),
            "frontend": detected.frontend,
            "backend": detected.backend,
            "llm_api": detected.llm_api,
            "deployment_platform": detected.deployment_platform,
            "confidence": detected.confidence,
            "raw_tags": detected.raw_tags or [],
        }
        upsert_resp = (
            client.table("detected_stacks")
            .upsert(payload, on_conflict="submission_id")
            .execute()
        )
        handle_response(upsert_resp)

        return {"status": "ok", "detected_stack": payload}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
