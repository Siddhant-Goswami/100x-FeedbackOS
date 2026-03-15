"""
Rubrics router.

Separate from the reviews router to avoid path collisions and match
the API spec: GET /rubrics/{assignment_id}.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from api.models.database import get_supabase_client
from api.models.schemas import RubricDimension
from api.services import rubric_service

router = APIRouter()


def db() -> Client:
    return get_supabase_client()


@router.get("/{assignment_id}", response_model=list[RubricDimension])
def get_rubric(
    assignment_id: UUID,
    client: Client = Depends(db),
) -> list[RubricDimension]:
    """
    Return the merged (universal base + stack overlay) rubric dimensions
    for a given assignment.  Stack overlay is selected based on the detected
    stack of the first submission for the assignment (if available).
    """
    try:
        return rubric_service.get_rubric_for_assignment(client, str(assignment_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
