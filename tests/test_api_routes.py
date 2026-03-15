"""
API integration tests.

Spins up the real FastAPI app with Supabase dependency-injected mocks
using app.dependency_overrides — the correct FastAPI testing pattern.
Tests routing, request validation, response shape, and error handling
end-to-end through the HTTP layer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Dummy env vars must be set before importing the app
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test_anon")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test_service")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_anthropic")
os.environ.setdefault("GITHUB_TOKEN", "test_github")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test_discord")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")
os.environ.setdefault("ENV", "test")

from api.main import app  # noqa: E402
from api.routers import (  # noqa: E402
    analytics,
    calibration,
    dialogue,
    examples,
    reviews,
    rubrics,
    submissions,
    webhooks,
)

client = TestClient(app, raise_server_exceptions=True)

# ---------------------------------------------------------------------------
# Stable test IDs
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc).isoformat()
RUBRIC_ID     = str(uuid.uuid4())
DIM_ID        = str(uuid.uuid4())
ASSIGNMENT_ID = str(uuid.uuid4())
SUBMISSION_ID = str(uuid.uuid4())
STUDENT_ID    = str(uuid.uuid4())
TA_ID         = str(uuid.uuid4())
REVIEW_ID     = str(uuid.uuid4())
SCORE_ID      = str(uuid.uuid4())
EXAMPLE_ID    = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Mock DB factory
# ---------------------------------------------------------------------------


def _make_resp(data):
    """Return a mock Supabase response object with .data and .error."""
    resp = MagicMock()
    resp.data = data
    resp.error = None
    return resp


def _mock_client(table_map: dict):
    """
    Build a mock Supabase client.
    table_map: { "table_name": <data to return from .execute()> }
    Data can be a list, dict, or None.
    """
    mock = MagicMock()

    def _table(name: str):
        data = table_map.get(name, [])
        chain = MagicMock()
        resp = _make_resp(data)
        for method in (
            "select", "eq", "neq", "in_", "not_", "is_",
            "order", "limit", "offset", "maybe_single", "single",
            "upsert", "insert", "update", "delete",
        ):
            getattr(chain, method).return_value = chain
        chain.execute.return_value = resp
        return chain

    mock.table.side_effect = _table
    return mock


@contextmanager
def _override(deps: dict):
    """
    Context manager that sets app.dependency_overrides for the given
    {dependency_fn: mock_client} mapping and clears them after.
    """
    for dep, mock in deps.items():
        app.dependency_overrides[dep] = lambda m=mock: m
    try:
        yield
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared test rows
# ---------------------------------------------------------------------------

SUBMISSION_ROW = {
    "id": SUBMISSION_ID,
    "assignment_id": ASSIGNMENT_ID,
    "student_id": STUDENT_ID,
    "ta_id": TA_ID,
    "github_repo_url": "https://github.com/test/repo",
    "commit_sha": "abc123",
    "status": "submitted",
    "is_flagged": False,
    "flag_note": None,
    "submitted_at": NOW,
    "created_at": NOW,
    "student": None,
    "assignment": None,
    "files": None,
    "detected_stack": None,
}

REVIEW_ROW = {
    "id": REVIEW_ID,
    "submission_id": SUBMISSION_ID,
    "ta_id": TA_ID,
    "status": "draft",
    "overall_comment": None,
    "submitted_at": None,
    "delivered_at": None,
    "created_at": NOW,
    "scores": None,
    "submission": None,
}

DIM_ROW = {
    "id": DIM_ID,
    "rubric_id": RUBRIC_ID,
    "name": "Error Handling",
    "description": "Checks for try/except around API calls.",
    "category": "error_handling",
    "sort_order": 2,
    "is_required": True,
    "stack_tags": [],
    "created_at": NOW,
}

SCORE_ROW = {
    "id": SCORE_ID,
    "review_id": REVIEW_ID,
    "dimension_id": DIM_ID,
    "score": "green",
    "comment": None,
    "action_item": None,
    "action_item_source": "ta_written",
    "is_flagged_for_help": False,
    "flag_note": None,
    "created_at": NOW,
    "updated_at": NOW,
    "dimension": None,
}

EXAMPLE_ROW = {
    "id": EXAMPLE_ID,
    "dimension_id": DIM_ID,
    "stack_tag": "streamlit",
    "score": "red",
    "comment": "No try/except around API call.",
    "action_item": "Wrap in try/except catching anthropic.APIError.",
    "was_acted_on": True,
    "source_review_id": None,
    "created_at": NOW,
}

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_returns_200(self):
        assert client.get("/health").status_code == 200

    def test_returns_status_ok(self):
        assert client.get("/health").json()["status"] == "ok"

    def test_returns_env_field(self):
        assert "env" in client.get("/health").json()


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


class TestSubmissions:
    def test_list_200(self):
        mock = _mock_client({"submissions": [SUBMISSION_ROW]})
        with _override({submissions.db: mock}):
            r = client.get("/submissions")
        assert r.status_code == 200

    def test_list_returns_items_and_total(self):
        mock = _mock_client({"submissions": [SUBMISSION_ROW]})
        with _override({submissions.db: mock}):
            body = client.get("/submissions").json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 1

    def test_list_status_filter_passes_through(self):
        mock = _mock_client({"submissions": [SUBMISSION_ROW]})
        with _override({submissions.db: mock}):
            r = client.get("/submissions?status=submitted")
        assert r.status_code == 200

    def test_get_single_200(self):
        mock = _mock_client({"submissions": SUBMISSION_ROW})
        with _override({submissions.db: mock}):
            r = client.get(f"/submissions/{SUBMISSION_ID}")
        assert r.status_code == 200

    def test_get_invalid_uuid_422(self):
        assert client.get("/submissions/not-a-uuid").status_code == 422


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------


class TestReviews:
    def test_create_returns_review(self):
        mock_review = MagicMock(**REVIEW_ROW)
        mock = _mock_client({})
        with _override({reviews.db: mock}), \
             patch("api.services.review_service.create_review", return_value=mock_review):
            r = client.post("/reviews", json={
                "submission_id": SUBMISSION_ID,
                "ta_id": TA_ID,
            })
        assert r.status_code == 200

    def test_create_missing_ta_id_422(self):
        assert client.post("/reviews", json={"submission_id": SUBMISSION_ID}).status_code == 422

    def test_get_scores_returns_list(self):
        mock = _mock_client({"review_scores": [SCORE_ROW]})
        with _override({reviews.db: mock}):
            r = client.get(f"/reviews/{REVIEW_ID}/scores")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upsert_score_green(self):
        mock_score = MagicMock(**SCORE_ROW)
        mock = _mock_client({})
        with _override({reviews.db: mock}), \
             patch("api.services.review_service.upsert_score", return_value=mock_score):
            r = client.post(f"/reviews/{REVIEW_ID}/scores", json={
                "dimension_id": DIM_ID,
                "score": "green",
            })
        assert r.status_code == 200

    def test_upsert_score_invalid_value_422(self):
        r = client.post(f"/reviews/{REVIEW_ID}/scores", json={
            "dimension_id": DIM_ID,
            "score": "purple",
        })
        assert r.status_code == 422

    def test_flag_for_help_returns_flagged(self):
        mock = _mock_client({"review_scores": SCORE_ROW, "reviews": REVIEW_ROW})
        with _override({reviews.db: mock}):
            r = client.post(f"/reviews/{REVIEW_ID}/flag-for-help", json={
                "dimension_id": DIM_ID,
                "note": "Not sure how to score this.",
            })
        assert r.status_code == 200
        assert r.json()["status"] == "flagged"

    def test_flag_for_help_missing_dimension_422(self):
        assert client.post(f"/reviews/{REVIEW_ID}/flag-for-help", json={}).status_code == 422

    def test_suggest_action_returns_keys(self):
        mock = _mock_client({
            "rubric_dimensions": DIM_ROW,
            "example_feedback": [],
        })
        with _override({reviews.db: mock}), \
             patch("api.services.llm_service.suggest_action_item",
                   new_callable=AsyncMock,
                   return_value={"suggested_action_item": "Add try/except", "reasoning": "No handling"}):
            r = client.post(f"/reviews/{REVIEW_ID}/suggest-action", json={
                "dimension_id": DIM_ID,
                "score": "red",
                "code_snippet": "client.messages.create(...)",
            })
        assert r.status_code == 200
        body = r.json()
        assert "suggested_action_item" in body
        assert "reasoning" in body

    def test_suggest_action_invalid_score_422(self):
        r = client.post(f"/reviews/{REVIEW_ID}/suggest-action", json={
            "dimension_id": DIM_ID,
            "score": "not_a_score",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rubrics
# ---------------------------------------------------------------------------


class TestRubrics:
    def test_get_rubric_returns_list(self):
        from api.models.schemas import RubricDimension, DimensionCategory
        mock_dim = RubricDimension(**DIM_ROW)
        mock = _mock_client({})
        with _override({rubrics.db: mock}), \
             patch("api.services.rubric_service.get_rubric_for_assignment",
                   return_value=[mock_dim]):
            r = client.get(f"/rubrics/{ASSIGNMENT_ID}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert r.json()[0]["name"] == "Error Handling"

    def test_get_rubric_invalid_uuid_422(self):
        assert client.get("/rubrics/not-a-uuid").status_code == 422


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------


class TestExamples:
    def test_get_by_dimension_200(self):
        mock = _mock_client({"example_feedback": [EXAMPLE_ROW]})
        with _override({examples.db: mock}):
            r = client.get(f"/examples/{DIM_ID}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_all_200(self):
        mock = _mock_client({"example_feedback": [EXAMPLE_ROW]})
        with _override({examples.db: mock}):
            r = client.get("/examples")
        assert r.status_code == 200

    def test_invalid_dim_uuid_422(self):
        assert client.get("/examples/not-a-uuid").status_code == 422


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_calibration_200(self):
        mock = _mock_client({
            "review_scores": [],
            "rubric_dimensions": [DIM_ROW],
            "reviews": [],
        })
        with _override({calibration.db: mock}):
            r = client.get(f"/calibration/{ASSIGNMENT_ID}")
        assert r.status_code == 200

    def test_my_vs_peers_200(self):
        mock = _mock_client({
            "review_scores": [],
            "rubric_dimensions": [DIM_ROW],
            "reviews": [],
        })
        with _override({calibration.db: mock}):
            r = client.get(f"/calibration/{ASSIGNMENT_ID}/my-vs-peers?ta_id={TA_ID}")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    def test_instructor_200(self):
        mock = _mock_client({
            "users": [],
            "reviews": [],
            "review_scores": [],
            "rubric_dimensions": [DIM_ROW],
            "comprehension_events": [],
        })
        with _override({analytics.db: mock}):
            r = client.get("/analytics/instructor")
        assert r.status_code == 200
        body = r.json()
        assert "comprehension_rate" in body
        assert "ta_adoption_rate" in body
        assert "rubric_consistency" in body

    def test_ta_200(self):
        mock = _mock_client({
            "reviews": [],
            "review_scores": [],
            "comprehension_events": [],
        })
        with _override({analytics.db: mock}):
            r = client.get(f"/analytics/ta/{TA_ID}")
        assert r.status_code == 200
        body = r.json()
        assert "reviews_submitted" in body
        assert "comprehension_rate" in body

    def test_ta_invalid_uuid_422(self):
        assert client.get("/analytics/ta/not-a-uuid").status_code == 422


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


def _sign(payload: bytes, secret: str = "test_secret") -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


PUSH_PAYLOAD = {
    "repository": {"html_url": "https://github.com/student/project"},
    "after": "deadbeef123",
    "pusher": {"name": "student-github"},
}


class TestWebhooks:
    def _post(self, payload: dict, sig: str | None = None, event: str = "push"):
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "X-GitHub-Event": event}
        if sig is not None:
            headers["X-Hub-Signature-256"] = sig
        return client.post("/webhooks/github", content=body, headers=headers)

    def test_valid_push_accepted(self):
        body = json.dumps(PUSH_PAYLOAD).encode()
        mock = _mock_client({
            "users": [],
            "submissions": {
                "id": SUBMISSION_ID,
                "github_repo_url": "https://github.com/student/project",
                "commit_sha": "deadbeef123",
            },
        })
        with _override({webhooks.service_db: mock}), \
             patch("api.routers.webhooks._run_stack_detection"):
            r = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": _sign(body),
                    "X-GitHub-Event": "push",
                },
            )
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

    def test_invalid_signature_401(self):
        r = self._post(PUSH_PAYLOAD, sig="sha256=badsig")
        assert r.status_code == 401

    def test_missing_signature_401(self):
        r = self._post(PUSH_PAYLOAD, sig=None)
        assert r.status_code == 401

    def test_non_push_event_ignored(self):
        body = json.dumps({}).encode()
        mock = _mock_client({})
        with _override({webhooks.service_db: mock}):
            r = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": _sign(body),
                    "X-GitHub-Event": "ping",
                },
            )
        assert r.status_code == 200
        assert r.json()["status"] == "ignored"


# ---------------------------------------------------------------------------
# Dialogue
# ---------------------------------------------------------------------------

DIALOGUE_ROW = {
    "id": str(uuid.uuid4()),
    "review_id": REVIEW_ID,
    "discord_message_id": None,
    "author_discord_id": "discord_user_123",
    "author_role": "student",
    "content": "What does error handling mean here?",
    "thread_id": None,
    "created_at": NOW,
}


class TestDialogue:
    def test_post_dialogue_200(self):
        mock = _mock_client({"dialogue_logs": DIALOGUE_ROW})
        with _override({dialogue.db: mock}):
            r = client.post("/dialogue", json={
                "review_id": REVIEW_ID,
                "author_discord_id": "discord_user_123",
                "author_role": "student",
                "content": "What does error handling mean here?",
            })
        assert r.status_code == 200

    def test_post_dialogue_missing_content_422(self):
        r = client.post("/dialogue", json={
            "review_id": REVIEW_ID,
            "author_discord_id": "discord_user_123",
            "author_role": "student",
            # missing "content"
        })
        assert r.status_code == 422
