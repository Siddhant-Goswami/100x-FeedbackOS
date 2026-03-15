"""
Pytest configuration for FeedbackOS tests.

Globally mocks supabase.create_client so that no test ever tries to
initialise a real Supabase connection.  Individual tests that need
specific query results should use app.dependency_overrides to inject
a tailored mock client.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Env vars — must be set before any api.* import
# ---------------------------------------------------------------------------

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test_anon")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test_service")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_anthropic")
os.environ.setdefault("GITHUB_TOKEN", "test_github")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test_discord")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")
os.environ.setdefault("ENV", "test")


# ---------------------------------------------------------------------------
# Session-scoped supabase mock — prevents JWT validation on fake credentials
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def mock_supabase_create_client():
    """
    Replace supabase.create_client with a MagicMock for the entire test
    session.  The returned mock client is a plain MagicMock — tests that
    need specific return values must override the FastAPI dependency via
    app.dependency_overrides.
    """
    dummy_client = MagicMock()
    with patch("supabase.create_client", return_value=dummy_client), \
         patch("api.models.database.create_client", return_value=dummy_client):
        yield dummy_client
