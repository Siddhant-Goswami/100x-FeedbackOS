"""
Notification service.

Sends Discord notifications to students when their review is ready,
and creates Discord threads for ongoing feedback dialogue.

Uses the Discord HTTP API directly (via httpx) so it can be called
from the FastAPI process without running a full bot instance.
"""

from __future__ import annotations

import logging

import httpx

from api.config import DISCORD_BOT_TOKEN, FASTAPI_URL

logger = logging.getLogger(__name__)

_DISCORD_API = "https://discord.com/api/v10"


def _headers() -> dict[str, str]:
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN is not set. Cannot send Discord notifications."
        )
    return {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# DM notification
# ---------------------------------------------------------------------------


async def send_feedback_notification(
    student_discord_id: str,
    review_id: str,
    student_name: str,
    project_title: str,
    feedback_url: str,
) -> bool:
    """
    Send a Direct Message to a student notifying them that their review
    is ready.

    1. Opens a DM channel with the user.
    2. Posts the notification message into that channel.

    Returns True on success, False on failure (logs the error).
    """
    try:
        async with httpx.AsyncClient(headers=_headers(), timeout=10.0) as http:
            # 1. Create/fetch DM channel
            dm_resp = await http.post(
                f"{_DISCORD_API}/users/@me/channels",
                json={"recipient_id": student_discord_id},
            )
            dm_resp.raise_for_status()
            channel_id = dm_resp.json()["id"]

            # 2. Send message
            full_url = f"{FASTAPI_URL}{feedback_url}"
            message = (
                f"Hi {student_name}! Your feedback for **{project_title}** is ready.\n\n"
                f"View your detailed feedback here: {full_url}\n\n"
                "Please read through the action items and reach out in your feedback "
                "thread if you have questions."
            )
            msg_resp = await http.post(
                f"{_DISCORD_API}/channels/{channel_id}/messages",
                json={"content": message},
            )
            msg_resp.raise_for_status()

        logger.info(
            "Discord DM sent to student %s for review %s.", student_discord_id, review_id
        )
        return True

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Discord HTTP error sending DM to %s: %s — %s",
            student_discord_id,
            exc.response.status_code,
            exc.response.text,
        )
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error sending DM to %s: %s", student_discord_id, exc
        )
        return False


# ---------------------------------------------------------------------------
# Thread creation
# ---------------------------------------------------------------------------


async def create_feedback_thread(
    channel_id: str,
    student_discord_id: str,
    review_id: str,
) -> dict | None:
    """
    Create a Discord forum/thread in a channel for ongoing review dialogue.

    Thread name format: feedback-{review_id}
    Returns the thread object dict on success, or None on failure.
    """
    try:
        thread_name = f"feedback-{review_id}"
        starter_message = (
            f"<@{student_discord_id}> Your feedback thread is now open. "
            "Ask questions or discuss your feedback here. "
            "Your TA will be notified of your messages."
        )

        async with httpx.AsyncClient(headers=_headers(), timeout=10.0) as http:
            resp = await http.post(
                f"{_DISCORD_API}/channels/{channel_id}/threads",
                json={
                    "name": thread_name,
                    "type": 11,  # GUILD_PUBLIC_THREAD
                    "message": {"content": starter_message},
                },
            )
            resp.raise_for_status()
            thread_data = resp.json()

        logger.info(
            "Discord thread created: %s for review %s.", thread_data.get("id"), review_id
        )
        return thread_data

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Discord HTTP error creating thread for review %s: %s — %s",
            review_id,
            exc.response.status_code,
            exc.response.text,
        )
        return None
    except Exception as exc:
        logger.error(
            "Unexpected error creating thread for review %s: %s", review_id, exc
        )
        return None
