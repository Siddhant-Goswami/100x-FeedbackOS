"""
Pydantic v2 schemas for all FeedbackOS entities.

Enums mirror the PostgreSQL ENUM types defined in the Supabase schema.
Pydantic models are used for both DB row representation and API
request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    student = "student"
    ta = "ta"
    instructor = "instructor"


class SubmissionStatus(str, Enum):
    submitted = "submitted"
    under_review = "under_review"
    reviewed = "reviewed"
    resubmitted = "resubmitted"


class ReviewStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    delivered = "delivered"


class ScoreValue(str, Enum):
    green = "green"
    yellow = "yellow"
    red = "red"
    not_applicable = "not_applicable"
    flagged_for_help = "flagged_for_help"


class ActionItemSource(str, Enum):
    ta_written = "ta_written"
    ai_suggested_accepted = "ai_suggested_accepted"
    ai_suggested_edited = "ai_suggested_edited"


class DimensionCategory(str, Enum):
    code_quality = "code_quality"
    error_handling = "error_handling"
    architecture = "architecture"
    llm_usage = "llm_usage"
    deployment = "deployment"
    documentation = "documentation"
    prompt_eng = "prompt_eng"
    stack_specific = "stack_specific"


class RubricType(str, Enum):
    universal = "universal"
    overlay = "overlay"


class AuthorRole(str, Enum):
    student = "student"
    ta = "ta"


# ---------------------------------------------------------------------------
# Core entity models
# ---------------------------------------------------------------------------


class User(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    discord_id: Optional[str] = None
    github_username: Optional[str] = None
    cohort_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


class Cohort(BaseModel):
    id: UUID
    name: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Assignment(BaseModel):
    id: UUID
    cohort_id: UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    rubric_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


class RubricDimension(BaseModel):
    id: UUID
    rubric_id: UUID
    name: str
    description: str
    category: DimensionCategory
    sort_order: int = 0
    is_required: bool = True
    stack_tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None


class Rubric(BaseModel):
    id: UUID
    name: str
    type: RubricType
    assignment_id: Optional[UUID] = None
    stack_tag: Optional[str] = None
    created_at: Optional[datetime] = None
    dimensions: Optional[list[RubricDimension]] = None


class DetectedStack(BaseModel):
    submission_id: Optional[UUID] = None
    frontend: Optional[str] = None
    backend: Optional[str] = None
    llm_api: Optional[str] = None
    deployment_platform: Optional[str] = None
    confidence: float = 0.0
    raw_tags: Optional[list[str]] = None
    detected_at: Optional[datetime] = None


class SubmissionFile(BaseModel):
    id: UUID
    submission_id: UUID
    filepath: str
    content_preview: Optional[str] = None
    created_at: Optional[datetime] = None


class Submission(BaseModel):
    id: UUID
    assignment_id: UUID
    student_id: UUID
    ta_id: Optional[UUID] = None
    github_repo_url: str
    commit_sha: Optional[str] = None
    status: SubmissionStatus = SubmissionStatus.submitted
    is_flagged: bool = False
    flag_note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # Joined data (populated in detail endpoints)
    student: Optional[User] = None
    assignment: Optional[Assignment] = None
    files: Optional[list[SubmissionFile]] = None
    detected_stack: Optional[DetectedStack] = None


class ReviewScore(BaseModel):
    id: UUID
    review_id: UUID
    dimension_id: UUID
    score: ScoreValue
    comment: Optional[str] = None
    action_item: Optional[str] = None
    action_item_source: Optional[ActionItemSource] = None
    is_flagged_for_help: bool = False
    flag_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined
    dimension: Optional[RubricDimension] = None


class Review(BaseModel):
    id: UUID
    submission_id: UUID
    ta_id: UUID
    status: ReviewStatus = ReviewStatus.draft
    overall_comment: Optional[str] = None
    submitted_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # Joined
    scores: Optional[list[ReviewScore]] = None
    submission: Optional[Submission] = None


class ExampleFeedback(BaseModel):
    id: UUID
    dimension_id: UUID
    stack_tag: Optional[str] = None
    score: ScoreValue
    comment: str
    action_item: Optional[str] = None
    was_acted_on: bool = False
    source_review_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


class DialogueLog(BaseModel):
    id: UUID
    review_id: UUID
    discord_message_id: Optional[str] = None
    author_discord_id: str
    author_role: AuthorRole
    content: str
    thread_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ComprehensionEvent(BaseModel):
    id: UUID
    review_id: UUID
    review_score_id: Optional[UUID] = None
    student_id: Optional[UUID] = None
    commit_sha: str
    commit_timestamp: datetime
    files_changed: list[str]
    addressed: bool
    hours_after_delivery: Optional[float] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateReviewRequest(BaseModel):
    submission_id: UUID
    ta_id: UUID


class UpdateReviewRequest(BaseModel):
    overall_comment: Optional[str] = None
    status: Optional[ReviewStatus] = None


class ScoreRequest(BaseModel):
    dimension_id: UUID
    score: ScoreValue
    comment: Optional[str] = None
    action_item: Optional[str] = None
    action_item_source: Optional[ActionItemSource] = ActionItemSource.ta_written


class SuggestActionRequest(BaseModel):
    dimension_id: UUID
    score: ScoreValue
    code_snippet: Optional[str] = None
    context: Optional[str] = None


class FlagForHelpRequest(BaseModel):
    dimension_id: UUID
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SubmissionListResponse(BaseModel):
    items: list[Submission]
    total: int


class ReviewDetailResponse(BaseModel):
    review: Review
    rubric_dimensions: list[RubricDimension]
    scores: list[ReviewScore]
    unscored_required: list[str]
