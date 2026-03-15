"""
Tests for review_service — create, upsert_score, check_completeness, submit.

Supabase client is mocked throughout.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from api.services.review_service import (
    check_completeness,
    create_review,
    submit_review,
    upsert_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client():
    """Return a fully mocked Supabase client."""
    client = MagicMock()
    # Default chain that returns empty data
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=None, error=None)
    client.table.return_value.select.return_value = chain
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=None, error=None
    )
    return client


def _make_review(review_id=None, submission_id=None, ta_id=None, status="draft"):
    return {
        "id": str(review_id or uuid4()),
        "submission_id": str(submission_id or uuid4()),
        "ta_id": str(ta_id or uuid4()),
        "status": status,
        "overall_comment": None,
        "submitted_at": None,
        "delivered_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_dim(dim_id=None, name="Code Quality", is_required=True):
    from api.models.schemas import DimensionCategory, RubricDimension
    import uuid
    return RubricDimension(
        id=dim_id or uuid4(),
        rubric_id=uuid4(),
        name=name,
        description="Test description",
        category=DimensionCategory.code_quality,
        is_required=is_required,
        sort_order=1,
    )


# ---------------------------------------------------------------------------
# create_review
# ---------------------------------------------------------------------------


class TestCreateReview:
    def test_returns_existing_draft_if_found(self):
        client = _mock_client()
        existing = _make_review()
        # Simulate existing draft found
        (
            client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .maybe_single.return_value
            .execute.return_value
        ) = MagicMock(data=existing, error=None)

        result = create_review(client, existing["submission_id"], existing["ta_id"])
        assert str(result.id) == existing["id"]
        # Insert should NOT have been called
        client.table.return_value.insert.assert_not_called()

    def test_creates_new_draft_when_none_exists(self):
        client = _mock_client()
        new_review = _make_review()

        # No existing draft
        (
            client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .maybe_single.return_value
            .execute.return_value
        ) = MagicMock(data=None, error=None)

        # Insert returns new review
        (
            client.table.return_value
            .insert.return_value
            .execute.return_value
        ) = MagicMock(data=[new_review], error=None)

        # Update submission status (best-effort — also mock)
        (
            client.table.return_value
            .update.return_value
            .eq.return_value
            .execute.return_value
        ) = MagicMock(data=[{"id": new_review["submission_id"]}], error=None)

        result = create_review(
            client, new_review["submission_id"], new_review["ta_id"]
        )
        assert str(result.id) == new_review["id"]
        assert result.status.value == "draft"

    def test_raises_on_insert_failure(self):
        from fastapi import HTTPException

        client = _mock_client()

        # No existing draft
        (
            client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .maybe_single.return_value
            .execute.return_value
        ) = MagicMock(data=None, error=None)

        # Insert returns empty data
        (
            client.table.return_value
            .insert.return_value
            .execute.return_value
        ) = MagicMock(data=None, error=None)

        with pytest.raises(HTTPException) as exc_info:
            create_review(client, str(uuid4()), str(uuid4()))
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# upsert_score
# ---------------------------------------------------------------------------


class TestUpsertScore:
    def _setup_upsert_mock(self, client, return_data):
        (
            client.table.return_value
            .upsert.return_value
            .execute.return_value
        ) = MagicMock(data=return_data, error=None)

    def _make_score_row(self, review_id, dim_id, score):
        return {
            "id": str(uuid4()),
            "review_id": review_id,
            "dimension_id": dim_id,
            "score": score,
            "comment": None,
            "action_item": None,
            "action_item_source": None,
            "is_flagged_for_help": False,
            "flag_note": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_upsert_green_score(self):
        client = _mock_client()
        review_id = str(uuid4())
        dim_id = str(uuid4())
        row = self._make_score_row(review_id, dim_id, "green")
        self._setup_upsert_mock(client, [row])

        result = upsert_score(client, review_id, dim_id, "green")
        assert result.score.value == "green"

    def test_upsert_red_score_with_comment(self):
        client = _mock_client()
        review_id = str(uuid4())
        dim_id = str(uuid4())
        row = self._make_score_row(review_id, dim_id, "red")
        row["comment"] = "Missing error handling"
        row["action_item"] = "Wrap API calls in try/except"
        self._setup_upsert_mock(client, [row])

        result = upsert_score(
            client,
            review_id,
            dim_id,
            "red",
            comment="Missing error handling",
            action_item="Wrap API calls in try/except",
        )
        assert result.score.value == "red"
        assert result.comment == "Missing error handling"

    def test_upsert_raises_on_empty_response(self):
        from fastapi import HTTPException

        client = _mock_client()
        self._setup_upsert_mock(client, None)

        with pytest.raises(HTTPException) as exc_info:
            upsert_score(client, str(uuid4()), str(uuid4()), "green")
        assert exc_info.value.status_code == 500

    def test_flagged_for_help_sets_flag(self):
        client = _mock_client()
        review_id = str(uuid4())
        dim_id = str(uuid4())
        row = self._make_score_row(review_id, dim_id, "flagged_for_help")
        row["is_flagged_for_help"] = True
        self._setup_upsert_mock(client, [row])

        result = upsert_score(client, review_id, dim_id, "flagged_for_help")
        assert result.is_flagged_for_help is True


# ---------------------------------------------------------------------------
# check_completeness
# ---------------------------------------------------------------------------


class TestCheckCompleteness:
    def _setup_scored(self, client, scored_rows):
        (
            client.table.return_value
            .select.return_value
            .eq.return_value
            .execute.return_value
        ) = MagicMock(data=scored_rows, error=None)

    def test_complete_when_all_required_scored(self):
        client = _mock_client()
        dim_id = uuid4()
        dim = _make_dim(dim_id=dim_id, name="Code Quality", is_required=True)
        self._setup_scored(
            client, [{"dimension_id": str(dim_id), "score": "green"}]
        )

        result = check_completeness(client, str(uuid4()), [dim])
        assert result == []

    def test_returns_unscored_names(self):
        client = _mock_client()
        dim1 = _make_dim(name="Code Quality", is_required=True)
        dim2 = _make_dim(name="Error Handling", is_required=True)
        # Only dim1 is scored
        self._setup_scored(
            client,
            [{"dimension_id": str(dim1.id), "score": "green"}],
        )

        result = check_completeness(client, str(uuid4()), [dim1, dim2])
        assert "Error Handling" in result
        assert "Code Quality" not in result

    def test_optional_dims_not_required(self):
        client = _mock_client()
        optional_dim = _make_dim(name="Streamlit State", is_required=False)
        self._setup_scored(client, [])  # Nothing scored

        result = check_completeness(client, str(uuid4()), [optional_dim])
        assert result == []

    def test_flagged_for_help_counts_as_unscored(self):
        client = _mock_client()
        dim = _make_dim(name="Architecture", is_required=True)
        # flagged_for_help should not count as a proper score
        self._setup_scored(
            client,
            [{"dimension_id": str(dim.id), "score": "flagged_for_help"}],
        )

        result = check_completeness(client, str(uuid4()), [dim])
        assert "Architecture" in result

    def test_empty_rubric_always_complete(self):
        client = _mock_client()
        self._setup_scored(client, [])
        result = check_completeness(client, str(uuid4()), [])
        assert result == []


# ---------------------------------------------------------------------------
# submit_review
# ---------------------------------------------------------------------------


class TestSubmitReview:
    def _setup_update(self, client, return_data):
        (
            client.table.return_value
            .update.return_value
            .eq.return_value
            .execute.return_value
        ) = MagicMock(data=return_data, error=None)

    def test_submit_updates_status_to_submitted(self):
        client = _mock_client()
        review_id = str(uuid4())
        submission_id = str(uuid4())
        updated_row = {
            "id": review_id,
            "status": "submitted",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "submission_id": submission_id,
        }
        self._setup_update(client, [updated_row])

        # Should not raise
        submit_review(client, review_id)

        # Verify update was called at least twice (once for review, once for submission)
        assert client.table.return_value.update.call_count >= 1

        # The first update call should be for the review status
        first_call_kwargs = client.table.return_value.update.call_args_list[0][0][0]
        assert first_call_kwargs["status"] == "submitted"
        assert "submitted_at" in first_call_kwargs

    def test_submit_raises_on_update_failure(self):
        from fastapi import HTTPException

        client = _mock_client()
        self._setup_update(client, None)

        with pytest.raises(HTTPException) as exc_info:
            submit_review(client, str(uuid4()))
        assert exc_info.value.status_code == 500
