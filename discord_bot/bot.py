"""
FeedbackOS Discord Bot.

Handles:
- Student DM notifications when a review is delivered.
- Feedback thread creation for post-review dialogue.
- Capturing messages from feedback threads and forwarding to the API.

Run with:
    python -m discord_bot.bot
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("feedbackos.bot")

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content
intents.members = True  # Required for role inspection

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@bot.event
async def on_ready() -> None:
    logger.info(
        "FeedbackOS bot connected as %s (ID: %s)", bot.user, bot.user.id if bot.user else "unknown"
    )
    logger.info("Connected to %d guild(s).", len(bot.guilds))
    # Load the message handler cog
    await bot.load_extension("discord_bot.handlers")


@bot.event
async def on_error(event: str, *args, **kwargs) -> None:
    logger.exception("Unhandled error in event %s", event)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@bot.command(name="feedback")
async def feedback_command(ctx: commands.Context) -> None:
    """
    !feedback — placeholder command.

    Students can use this in a server channel to get a link to their
    latest feedback. In a full implementation this would look up the
    student's latest review and DM them the link.
    """
    await ctx.reply(
        "Your feedback is available in the FeedbackOS app. "
        "Check your DMs for the direct link, or ask your TA."
    )


# ---------------------------------------------------------------------------
# Exposed async helpers (called from notification_service)
# ---------------------------------------------------------------------------


async def send_dm(user_id: str | int, message: str) -> bool:
    """
    Send a DM to a Discord user by ID.

    Returns True on success, False on failure.
    """
    try:
        uid = int(user_id)
        user = await bot.fetch_user(uid)
        dm_channel = await user.create_dm()
        await dm_channel.send(message)
        logger.info("DM sent to user %s.", uid)
        return True
    except discord.NotFound:
        logger.warning("User %s not found when attempting DM.", user_id)
        return False
    except discord.Forbidden:
        logger.warning("Cannot DM user %s (DMs disabled or blocked).", user_id)
        return False
    except Exception as exc:
        logger.error("Error sending DM to %s: %s", user_id, exc)
        return False


async def create_thread(
    channel_id: str | int,
    name: str,
    message: str,
) -> discord.Thread | None:
    """
    Create a public thread in a channel.

    Returns the Thread object on success, None on failure.
    """
    try:
        cid = int(channel_id)
        channel = await bot.fetch_channel(cid)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Channel %s is not a TextChannel — cannot create thread.", cid)
            return None

        thread = await channel.create_thread(
            name=name,
            type=discord.ChannelType.public_thread,
        )
        await thread.send(message)
        logger.info("Thread '%s' created in channel %s.", name, cid)
        return thread

    except discord.Forbidden:
        logger.error("Missing permissions to create thread in channel %s.", channel_id)
        return None
    except Exception as exc:
        logger.error("Error creating thread in channel %s: %s", channel_id, exc)
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    if not DISCORD_BOT_TOKEN:
        logger.error(
            "DISCORD_BOT_TOKEN is not set. Set it in .env before running the bot."
        )
        sys.exit(1)
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run()
