"""
LLM service.

Uses the Anthropic SDK to power two capabilities:
1. Stack detection — classify the tech stack from a repo file tree.
2. Action item suggestion — suggest concrete next steps for a rubric score.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import anthropic

from api.config import ANTHROPIC_API_KEY
from api.models.schemas import DetectedStack

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Cannot make LLM calls."
            )
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Stack detection
# ---------------------------------------------------------------------------

_DETECT_STACK_SYSTEM = """\
You are a software stack classifier for student capstone projects.
Given a list of repository file paths and snippets from key files, identify:
- frontend: the primary frontend framework/library (e.g. "streamlit", "gradio", "react", "vanilla_js", "none")
- backend: the primary backend framework (e.g. "fastapi", "flask", "django", "none")
- llm_api: the LLM API being used (e.g. "openai", "anthropic", "cohere", "ollama", "none")
- deployment_platform: inferred deployment target (e.g. "streamlit_cloud", "railway", "render", "vercel", "heroku", "none", "unknown")
- confidence: a float 0.0–1.0 indicating how confident you are
- raw_tags: list of additional technology tags (e.g. ["supabase", "sqlite", "redis"])

Respond ONLY with a JSON object matching this exact schema:
{
  "frontend": "...",
  "backend": "...",
  "llm_api": "...",
  "deployment_platform": "...",
  "confidence": 0.0,
  "raw_tags": []
}
Do not include any explanation or markdown fences.
"""


async def detect_stack(
    file_tree: list[str],
    key_file_snippets: dict[str, str],
) -> DetectedStack:
    """
    Classify the tech stack of a project from its file tree and key snippets.

    Returns a DetectedStack with all fields populated (or "unknown"/None on
    parse failure).
    """
    # Build a compact prompt — keep total input well under 4K tokens
    tree_sample = "\n".join(file_tree[:200])
    snippets_text = ""
    for filename, content in key_file_snippets.items():
        snippets_text += f"\n--- {filename} ---\n{content}\n"

    user_message = (
        f"File tree (first 200 entries):\n{tree_sample}\n\n"
        f"Key file snippets:{snippets_text}"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_DETECT_STACK_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text.strip()
        data = json.loads(raw_text)

        return DetectedStack(
            frontend=data.get("frontend"),
            backend=data.get("backend"),
            llm_api=data.get("llm_api"),
            deployment_platform=data.get("deployment_platform"),
            confidence=float(data.get("confidence", 0.0)),
            raw_tags=data.get("raw_tags", []),
        )

    except json.JSONDecodeError as exc:
        logger.warning("Stack detection returned malformed JSON: %s", exc)
        return DetectedStack(confidence=0.0)
    except anthropic.APIError as exc:
        logger.error("Anthropic API error during stack detection: %s", exc)
        return DetectedStack(confidence=0.0)
    except Exception as exc:
        logger.error("Unexpected error during stack detection: %s", exc)
        return DetectedStack(confidence=0.0)


# ---------------------------------------------------------------------------
# Action item suggestion
# ---------------------------------------------------------------------------

_SUGGEST_ACTION_SYSTEM = """\
You are an expert code reviewer helping teaching assistants write actionable feedback
for student projects. Given a rubric dimension, a score, a code snippet (if provided),
and examples of good feedback, suggest a concrete and specific action item the student
should take to improve.

Your response MUST be a JSON object with exactly these two keys:
{
  "suggested_action_item": "A clear, specific, actionable instruction for the student.",
  "reasoning": "Brief explanation of why this is the right action for this score."
}
Do not include markdown fences or any other text outside the JSON.
"""


async def suggest_action_item(
    dimension_name: str,
    dimension_desc: str,
    score: str,
    code_snippet: str,
    examples: list[dict[str, Any]],
) -> dict[str, str]:
    """
    Suggest a concrete action item for a given dimension score.

    Keeps the prompt under ~3K tokens by trimming code_snippet and examples.
    Returns a dict with 'suggested_action_item' and 'reasoning'.
    On any error returns a safe fallback dict.
    """
    # Trim code snippet to ~1500 chars to stay within budget
    snippet_trimmed = (code_snippet or "")[:1500]
    if len(code_snippet or "") > 1500:
        snippet_trimmed += "\n... [truncated]"

    # Format up to 3 examples
    example_lines = []
    for ex in examples[:3]:
        ex_score = ex.get("score", "")
        ex_comment = ex.get("comment", "")
        ex_action = ex.get("action_item", "")
        example_lines.append(
            f"  Example ({ex_score}):\n    Comment: {ex_comment}\n    Action: {ex_action}"
        )
    examples_text = "\n".join(example_lines) if example_lines else "  (none available)"

    user_message = (
        f"Dimension: {dimension_name}\n"
        f"Description: {dimension_desc}\n"
        f"Score given: {score}\n\n"
        f"Code snippet:\n{snippet_trimmed or '(none provided)'}\n\n"
        f"Reference examples:\n{examples_text}"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SUGGEST_ACTION_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text.strip()
        data = json.loads(raw_text)

        return {
            "suggested_action_item": data.get("suggested_action_item", ""),
            "reasoning": data.get("reasoning", ""),
        }

    except json.JSONDecodeError as exc:
        logger.warning("Suggest action returned malformed JSON: %s", exc)
        return {
            "suggested_action_item": "Please review this dimension and address the identified issues.",
            "reasoning": "Could not parse LLM response.",
        }
    except anthropic.APIError as exc:
        logger.error("Anthropic API error during suggest_action: %s", exc)
        return {
            "suggested_action_item": "Please review this dimension and address the identified issues.",
            "reasoning": f"API error: {exc}",
        }
    except Exception as exc:
        logger.error("Unexpected error during suggest_action: %s", exc)
        return {
            "suggested_action_item": "Please review this dimension and address the identified issues.",
            "reasoning": f"Unexpected error: {exc}",
        }
