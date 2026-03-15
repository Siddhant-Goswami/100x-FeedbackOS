"""
Examples router.

Serves curated example feedback entries, optionally filtered by
dimension and/or tech stack.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.models.database import get_supabase_client, handle_response
from api.models.schemas import ExampleFeedback

router = APIRouter()


def db() -> Client:
    return get_supabase_client()


@router.get("/{dimension_id}", response_model=list[ExampleFeedback])
def get_examples_for_dimension(
    dimension_id: UUID,
    stack_filter: Optional[str] = Query(
        None, description="Optional stack tag to filter examples (e.g. 'streamlit')"
    ),
    client: Client = Depends(db),
) -> list[ExampleFeedback]:
    """
    Return example feedback entries for a specific rubric dimension.
    Optionally filter by stack_tag.
    """
    try:
        query = (
            client.table("example_feedback")
            .select("*")
            .eq("dimension_id", str(dimension_id))
        )
        if stack_filter:
            # Include examples with matching stack OR no stack (universal)
            query = query.or_(
                f"stack_tag.eq.{stack_filter},stack_tag.is.null"
            )
        query = query.order("was_acted_on", desc=True)
        resp = query.execute()
        data = handle_response(resp)
        return [ExampleFeedback(**row) for row in data]

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=dict)
def get_all_examples(
    client: Client = Depends(db),
) -> dict:
    """
    Return all example feedback entries grouped by dimension_id.
    Useful for the examples browsing page.
    """
    try:
        resp = (
            client.table("example_feedback")
            .select("*, dimension:rubric_dimensions(id, name, category)")
            .order("dimension_id")
            .execute()
        )
        data = handle_response(resp)

        grouped: dict[str, list] = {}
        for row in data:
            dim_id = str(row.get("dimension_id", "unknown"))
            grouped.setdefault(dim_id, []).append(row)

        return {"examples": grouped, "total": len(data)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
