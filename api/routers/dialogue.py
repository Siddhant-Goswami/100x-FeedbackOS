"""
Dialogue router.

Logs messages from Discord feedback threads so instructors can track
post-review student-TA interactions.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client
from typing import Optional
from uuid import UUID

from api.models.database import get_service_client, handle_response
from api.models.schemas import AuthorRole, DialogueLog

router = APIRouter()


def db() -> Client:
    return get_service_client()


class LogDialogueRequest(BaseModel):
    review_id: UUID
    discord_message_id: Optional[str] = None
    author_discord_id: str
    author_role: AuthorRole
    content: str
    thread_id: Optional[str] = None


@router.post("", response_model=DialogueLog)
def log_dialogue(
    body: LogDialogueRequest,
    client: Client = Depends(db),
) -> DialogueLog:
    """
    Persist a single dialogue message from a Discord feedback thread.

    Called by the Discord bot whenever a new message is posted in a
    thread whose name matches `feedback-{review_id}`.
    """
    try:
        payload = {
            "review_id": str(body.review_id),
            "discord_message_id": body.discord_message_id,
            "author_discord_id": body.author_discord_id,
            "author_role": body.author_role.value,
            "content": body.content,
            "thread_id": body.thread_id,
        }
        resp = client.table("dialogue_logs").insert(payload).execute()
        data = handle_response(resp)
        if isinstance(data, list):
            data = data[0]
        return DialogueLog(**data)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
