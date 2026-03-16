"""
Submissions router.

Handles listing/fetching student project submissions and triggering
automated stack detection.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from api.models.database import get_supabase_client, get_service_client, handle_response
from api.models.schemas import Submission, SubmissionListResponse
from api.services import llm_service

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Ingest endpoint — replaces GitHub webhook
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    github_repo_url: str
    student_email: Optional[str] = None
    assignment_id: Optional[str] = "a0000000-0000-0000-0000-000000000001"
    ta_email: Optional[str] = None


@router.post("/ingest")
def ingest_repo(body: IngestRequest) -> dict:
    """
    Accept a public GitHub repo URL, ingest its code via gitingest,
    create a submission record, and store the content for review.
    """
    try:
        from gitingest import ingest as _ingest
    except ImportError:
        raise HTTPException(status_code=500, detail="gitingest is not installed.")

    # 1. Fetch code via gitingest
    # Only pass a token if it looks like a real GitHub token; ignore placeholders.
    import os as _os
    raw_token = _os.environ.get("GITHUB_TOKEN", "")
    gh_token = raw_token if raw_token.startswith(("ghp_", "github_pat_", "ghs_")) else None

    try:
        summary, tree, content = _ingest(body.github_repo_url, token=gh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not ingest repo '{body.github_repo_url}': {exc}",
        )

    svc_client = get_service_client()

    # 2. Resolve student_id and ta_id from emails
    student_id: Optional[str] = None
    ta_id: Optional[str] = None

    if body.student_email:
        resp = svc_client.table("users").select("id").eq("email", body.student_email).maybe_single().execute()
        if resp.data:
            student_id = resp.data["id"]

    if body.ta_email:
        resp = svc_client.table("users").select("id").eq("email", body.ta_email).maybe_single().execute()
        if resp.data:
            ta_id = resp.data["id"]

    # 3. Upsert submission record (NULL commit_sha → unique per repo_url)
    sub_payload: dict = {
        "github_repo_url": body.github_repo_url,
        "commit_sha": None,
        "status": "submitted",
        "assignment_id": body.assignment_id,
    }
    if student_id:
        sub_payload["student_id"] = student_id
    if ta_id:
        sub_payload["ta_id"] = ta_id

    sub_resp = (
        svc_client.table("submissions")
        .upsert(sub_payload, on_conflict="github_repo_url,commit_sha")
        .execute()
    )
    sub_data = handle_response(sub_resp)
    if isinstance(sub_data, list):
        sub_data = sub_data[0]
    submission_id = sub_data["id"]

    # 4. Store gitingest output in submission_files
    svc_client.table("submission_files").upsert(
        {"submission_id": submission_id, "filepath": "_gitingest_tree",
         "content_preview": f"{summary}\n\n{tree}"[:10_000]},
        on_conflict="submission_id,filepath",
    ).execute()
    svc_client.table("submission_files").upsert(
        {"submission_id": submission_id, "filepath": "_gitingest_content",
         "content_preview": content[:150_000]},
        on_conflict="submission_id,filepath",
    ).execute()

    # 5. Stack detection from ingested tree
    try:
        import asyncio
        file_lines = [l.strip() for l in tree.splitlines() if l.strip()]
        detected = asyncio.run(llm_service.detect_stack(file_lines[:200], {"summary": summary[:3000]}))
        svc_client.table("detected_stacks").upsert(
            {"submission_id": submission_id, "frontend": detected.frontend,
             "backend": detected.backend, "llm_api": detected.llm_api,
             "deployment_platform": detected.deployment_platform,
             "confidence": detected.confidence, "raw_tags": detected.raw_tags or []},
            on_conflict="submission_id",
        ).execute()
    except Exception as exc:
        logger.warning("Stack detection failed for %s: %s", body.github_repo_url, exc)

    return {
        "status": "ok",
        "submission_id": submission_id,
        "repo_url": body.github_repo_url,
        "content_length": len(content),
    }
