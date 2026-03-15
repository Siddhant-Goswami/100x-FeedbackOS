"""
Supabase client setup.

Two clients are exposed:
- Anon client  — for user-authenticated requests (RLS enforced)
- Service client — for server-side privileged operations (bypasses RLS)
"""

from fastapi import HTTPException
from supabase import create_client, Client

from api.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY


def get_supabase_client() -> Client:
    """
    Return an anon/public Supabase client.

    Intended for use in FastAPI dependency injection where the caller
    is an authenticated user and Row Level Security should be enforced.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set before creating a client."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_service_client() -> Client:
    """
    Return a service-role Supabase client.

    Bypasses Row Level Security — use only for trusted server-side operations
    such as webhook handlers, background jobs, or admin seeding scripts.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set before creating a "
            "service client."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def handle_response(response) -> dict | list:
    """
    Validate a Supabase query response and return its data.

    Raises:
        HTTPException 404 — if the query returned no rows.
        HTTPException 500 — if the Supabase response contains an error.

    Returns the `.data` field of the response on success.
    """
    # supabase-py >= 2.x raises exceptions itself on network errors,
    # but a successful HTTP call with a Postgres error surfaces here.
    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {response.error.message}",
        )

    data = response.data if hasattr(response, "data") else response

    if data is None:
        raise HTTPException(status_code=404, detail="Resource not found.")

    return data
