"""
Configuration module — loads all environment variables and exposes
module-level constants used throughout the API.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY", "")

# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET: str = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------
DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID: str = os.environ.get("DISCORD_GUILD_ID", "")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
FASTAPI_URL: str = os.environ.get("FASTAPI_URL", "http://localhost:8000")
ENV: str = os.environ.get("ENV", "development")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RUBRIC_DIR: Path = _ROOT / "rubrics"

# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------

def is_development() -> bool:
    return ENV == "development"


def validate_config() -> list[str]:
    """Return list of missing required config keys (for startup warnings)."""
    required = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
    }
    return [k for k, v in required.items() if not v]
