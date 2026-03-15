"""
Tests for llm_service — stack detection and action item suggestion.

Anthropic client is mocked to avoid real API calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.llm_service import detect_stack, suggest_action_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_anthropic_response(text: str) -> MagicMock:
    """Create a mock anthropic.Message with a text content block."""
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ---------------------------------------------------------------------------
# detect_stack
# ---------------------------------------------------------------------------


class TestDetectStack:
    VALID_RESPONSE = json.dumps(
        {
            "frontend": "streamlit",
            "backend": "none",
            "llm_api": "anthropic",
            "deployment_platform": "streamlit_cloud",
            "confidence": 0.95,
            "raw_tags": ["supabase", "python"],
        }
    )

    STREAMLIT_FILE_TREE = [
        "app.py",
        "requirements.txt",
        "pages/1_Chat.py",
        ".streamlit/config.toml",
        "services/llm.py",
    ]

    STREAMLIT_KEY_FILES = {
        "requirements.txt": "streamlit>=1.32.0\nanthropic>=0.18.0\nsupabase>=2.3.0\n",
        "app.py": "import streamlit as st\nimport anthropic\n",
    }

    @pytest.mark.asyncio
    async def test_returns_detected_stack_on_valid_response(self):
        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                self.VALID_RESPONSE
            )
            mock_get.return_value = mock_client

            result = await detect_stack(self.STREAMLIT_FILE_TREE, self.STREAMLIT_KEY_FILES)

        assert result.frontend == "streamlit"
        assert result.llm_api == "anthropic"
        assert result.confidence == 0.95
        assert "supabase" in (result.raw_tags or [])

    @pytest.mark.asyncio
    async def test_returns_empty_stack_on_malformed_json(self):
        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                "This is not JSON at all."
            )
            mock_get.return_value = mock_client

            result = await detect_stack(self.STREAMLIT_FILE_TREE, {})

        assert result.confidence == 0.0
        assert result.frontend is None

    @pytest.mark.asyncio
    async def test_returns_empty_stack_on_api_error(self):
        import anthropic

        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = anthropic.APIConnectionError(
                request=MagicMock()
            )
            mock_get.return_value = mock_client

            result = await detect_stack(self.STREAMLIT_FILE_TREE, {})

        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_handles_empty_file_tree(self):
        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                json.dumps(
                    {
                        "frontend": "unknown",
                        "backend": "unknown",
                        "llm_api": "none",
                        "deployment_platform": "unknown",
                        "confidence": 0.1,
                        "raw_tags": [],
                    }
                )
            )
            mock_get.return_value = mock_client

            result = await detect_stack([], {})

        assert result is not None
        assert result.confidence == 0.1

    @pytest.mark.asyncio
    async def test_truncates_large_file_tree(self):
        """Ensure the service doesn't crash or blow up tokens on large trees."""
        large_tree = [f"src/module_{i}.py" for i in range(1000)]

        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                self.VALID_RESPONSE
            )
            mock_get.return_value = mock_client

            result = await detect_stack(large_tree, {})

        # Verify the API was called (only once)
        assert mock_client.messages.create.call_count == 1

        # Verify the prompt input was trimmed (check the user message)
        call_args = mock_client.messages.create.call_args
        user_message = call_args.kwargs.get("messages", [{}])[0].get("content", "")
        # Should contain at most 200 file entries (hard-coded limit in llm_service)
        file_lines = [
            line for line in user_message.split("\n") if "module_" in line
        ]
        assert len(file_lines) <= 200

    @pytest.mark.asyncio
    async def test_uses_haiku_model(self):
        """Ensure the cheap/fast model is used for stack detection."""
        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                self.VALID_RESPONSE
            )
            mock_get.return_value = mock_client

            await detect_stack(["app.py"], {"app.py": "import streamlit"})

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "haiku" in call_kwargs.get("model", "")


# ---------------------------------------------------------------------------
# suggest_action_item
# ---------------------------------------------------------------------------


class TestSuggestActionItem:
    VALID_SUGGESTION = json.dumps(
        {
            "suggested_action_item": "Wrap your API call in a try/except block.",
            "reasoning": "The score is red because there is no error handling.",
        }
    )

    @pytest.mark.asyncio
    async def test_returns_action_and_reasoning_on_valid_response(self):
        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                self.VALID_SUGGESTION
            )
            mock_get.return_value = mock_client

            result = await suggest_action_item(
                dimension_name="Error Handling",
                dimension_desc="Graceful error handling",
                score="red",
                code_snippet="client.messages.create()",
                examples=[],
            )

        assert "suggested_action_item" in result
        assert "reasoning" in result
        assert len(result["suggested_action_item"]) > 0

    @pytest.mark.asyncio
    async def test_fallback_on_malformed_json(self):
        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                "Here is my suggestion: add error handling."
            )
            mock_get.return_value = mock_client

            result = await suggest_action_item(
                dimension_name="Error Handling",
                dimension_desc="Graceful failures",
                score="red",
                code_snippet="",
                examples=[],
            )

        # Should return fallback dict, not raise
        assert "suggested_action_item" in result
        assert len(result["suggested_action_item"]) > 0

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        import anthropic

        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = anthropic.RateLimitError(
                message="Rate limit", response=MagicMock(), body={}
            )
            mock_get.return_value = mock_client

            result = await suggest_action_item(
                dimension_name="Code Quality",
                dimension_desc="Structure",
                score="yellow",
                code_snippet="",
                examples=[],
            )

        assert "suggested_action_item" in result
        assert "API error" in result.get("reasoning", "")

    @pytest.mark.asyncio
    async def test_code_snippet_truncated_to_budget(self):
        """Code snippets over 1500 chars should be truncated before sending."""
        long_snippet = "x = 1\n" * 500  # ~3000 chars

        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                self.VALID_SUGGESTION
            )
            mock_get.return_value = mock_client

            await suggest_action_item(
                dimension_name="Code Quality",
                dimension_desc="Structure",
                score="red",
                code_snippet=long_snippet,
                examples=[],
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_msg = call_kwargs.get("messages", [{}])[0].get("content", "")
        # The user message should contain the truncation marker
        assert "[truncated]" in user_msg

    @pytest.mark.asyncio
    async def test_max_three_examples_used(self):
        """Only the first 3 examples should be included in the prompt."""
        examples = [
            {"score": "red", "comment": f"Example {i}", "action_item": f"Fix {i}"}
            for i in range(10)
        ]

        with patch("api.services.llm_service._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _make_anthropic_response(
                self.VALID_SUGGESTION
            )
            mock_get.return_value = mock_client

            await suggest_action_item(
                dimension_name="Code Quality",
                dimension_desc="Structure",
                score="red",
                code_snippet="",
                examples=examples,
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_msg = call_kwargs.get("messages", [{}])[0].get("content", "")

        # Only "Example 0", "Example 1", "Example 2" should appear
        assert "Example 3" not in user_msg
        assert "Example 0" in user_msg
