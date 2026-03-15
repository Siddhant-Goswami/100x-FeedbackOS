"""
Webhooks router.

Handles inbound GitHub push events.  Each push creates or updates a
Submission record, then asynchronously triggers stack detection.
"""

import hashlib
import hmac
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from supabase import Client

from api.config import GITHUB_WEBHOOK_SECRET
from api.models.database import get_service_client, handle_response
from api.services import github_service, llm_service

logger = logging.getLogger(__name__)

router = APIRouter()


def service_db() -> Client:
    return get_service_client()


# ---------------------------------------------------------------------------
# HMAC validation helper
# ---------------------------------------------------------------------------


def _verify_github_signature(payload: bytes, signature_header: Optional[str]) -> None:
    """
    Validate the X-Hub-Signature-256 header sent by GitHub.

    Raises HTTPException 401 if the signature is missing or invalid.
    Skips validation if GITHUB_WEBHOOK_SECRET is not configured (dev mode).
    """
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning(
            "GITHUB_WEBHOOK_SECRET not set — skipping webhook signature validation."
        )
        return

    if not signature_header:
        raise HTTPException(
            status_code=401, detail="Missing X-Hub-Signature-256 header."
        )

    algorithm, _, digest = signature_header.partition("=")
    if algorithm != "sha256":
        raise HTTPException(
            status_code=401, detail="Unsupported signature algorithm."
        )

    expected = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, digest):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    client: Client = Depends(service_db),
) -> dict:
    """
    Receive GitHub push events.

    1. Validate HMAC signature.
    2. Parse push payload.
    3. Upsert a Submission record.
    4. Schedule async stack detection.
    """
    raw_body = await request.body()

    # Validate signature
    _verify_github_signature(raw_body, x_hub_signature_256)

    # We only care about push events
    if x_github_event and x_github_event != "push":
        return {"status": "ignored", "event": x_github_event}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    repo_url: str = payload.get("repository", {}).get("html_url", "")
    commit_sha: str = payload.get("after", "")
    pusher_username: str = payload.get("pusher", {}).get("name", "")

    if not repo_url:
        raise HTTPException(status_code=400, detail="Missing repository.html_url in payload.")

    logger.info("GitHub push received: repo=%s sha=%s", repo_url, commit_sha)

    # Look up student by GitHub username
    student_id: Optional[str] = None
    if pusher_username:
        user_resp = (
            client.table("users")
            .select("id")
            .eq("github_username", pusher_username)
            .maybe_single()
            .execute()
        )
        if user_resp.data:
            student_id = user_resp.data["id"]

    # Upsert submission (idempotent on repo_url + commit_sha)
    submission_payload: dict = {
        "github_repo_url": repo_url,
        "commit_sha": commit_sha,
        "status": "submitted",
    }
    if student_id:
        submission_payload["student_id"] = student_id

    upsert_resp = (
        client.table("submissions")
        .upsert(submission_payload, on_conflict="github_repo_url,commit_sha")
        .execute()
    )
    upsert_data = handle_response(upsert_resp)
    if isinstance(upsert_data, list):
        upsert_data = upsert_data[0]

    submission_id: str = upsert_data["id"]

    # Schedule async stack detection
    background_tasks.add_task(
        _run_stack_detection, submission_id, repo_url, commit_sha, client
    )

    return {
        "status": "accepted",
        "submission_id": submission_id,
        "stack_detection": "scheduled",
    }


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _run_stack_detection(
    submission_id: str,
    repo_url: str,
    commit_sha: str,
    client: Client,
) -> None:
    """Background task: detect stack and persist result."""
    try:
        file_tree = await github_service.fetch_repo_files(repo_url, commit_sha)
        key_snippets = await github_service.parse_key_files(repo_url)
        detected = await llm_service.detect_stack(file_tree, key_snippets)

        payload = {
            "submission_id": submission_id,
            "frontend": detected.frontend,
            "backend": detected.backend,
            "llm_api": detected.llm_api,
            "deployment_platform": detected.deployment_platform,
            "confidence": detected.confidence,
            "raw_tags": detected.raw_tags or [],
        }
        client.table("detected_stacks").upsert(
            payload, on_conflict="submission_id"
        ).execute()
        logger.info("Stack detection complete for submission %s", submission_id)

    except Exception as exc:
        logger.error(
            "Stack detection failed for submission %s: %s", submission_id, exc
        )
