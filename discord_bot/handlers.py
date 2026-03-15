"""
Discord message handlers cog.

Captures messages posted in feedback threads (named feedback-{review_id})
and forwards them to the FeedbackOS API /dialogue endpoint.

Author role is determined by whether the sender has a "TA" role in the
Discord guild.
"""

from __future__ import annotations

import logging
import os
import re

import discord
import httpx
from discord.ext import commands

FASTAPI_URL: str = os.environ.get("FASTAPI_URL", "http://localhost:8000")
DISCORD_GUILD_ID: str = os.environ.get("DISCORD_GUILD_ID", "")

logger = logging.getLogger("feedbackos.handlers")

# Thread name pattern: feedback-{uuid}
_FEEDBACK_THREAD_RE = re.compile(
    r"^feedback-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def _extract_review_id(thread_name: str) -> str | None:
    """Extract review UUID from a thread name like 'feedback-{uuid}'."""
    match = _FEEDBACK_THREAD_RE.match(thread_name.strip())
    return match.group(1) if match else None


def _is_ta(member: discord.Member) -> bool:
    """Return True if the guild member has a role named 'TA' (case-insensitive)."""
    return any(role.name.lower() == "ta" for role in member.roles)


class FeedbackHandlers(commands.Cog):
    """Cog that listens for messages in feedback threads."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Triggered for every message the bot can see.

        Filters:
        - Ignores bot messages (including self).
        - Only processes messages in threads whose name matches feedback-{uuid}.
        - Posts to /dialogue with author_role inferred from guild roles.
        """
        # Ignore bots
        if message.author.bot:
            return

        # Only handle messages inside threads
        if not isinstance(message.channel, discord.Thread):
            return

        thread: discord.Thread = message.channel
        review_id = _extract_review_id(thread.name)
        if not review_id:
            return  # Not a feedback thread

        # Determine author role
        author_role = "student"
        if isinstance(message.author, discord.Member) and _is_ta(message.author):
            author_role = "ta"

        payload = {
            "review_id": review_id,
            "discord_message_id": str(message.id),
            "author_discord_id": str(message.author.id),
            "author_role": author_role,
            "content": message.content,
            "thread_id": str(thread.id),
        }

        # Forward to API (fire-and-forget with error logging)
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.post(f"{FASTAPI_URL}/dialogue", json=payload)
                if resp.status_code not in (200, 201):
                    logger.warning(
                        "Dialogue API returned %s for message %s in thread %s",
                        resp.status_code,
                        message.id,
                        thread.name,
                    )
                else:
                    logger.debug(
                        "Logged dialogue message %s from %s (role=%s) in thread %s",
                        message.id,
                        message.author,
                        author_role,
                        thread.name,
                    )
        except httpx.RequestError as exc:
            logger.error(
                "Failed to post dialogue message %s to API: %s", message.id, exc
            )


# ---------------------------------------------------------------------------
# Cog setup (called by bot.load_extension)
# ---------------------------------------------------------------------------


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FeedbackHandlers(bot))
