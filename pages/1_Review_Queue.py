"""
Review Queue page — for TAs.

Shows all submissions assigned to the logged-in TA, with filtering,
sorting, and status indicators. Clicking a card opens the review screen.
"""

import os
from datetime import datetime, timezone

import httpx
import streamlit as st

def _st_secret(k, d=""):
    try:
        import streamlit as _st
        return _st.secrets[k]
    except Exception:
        import os as _os
        return _os.environ.get(k, d)
FASTAPI_URL = _st_secret("FASTAPI_URL", "http://localhost:8000")

st.set_page_config(page_title="Review Queue — FeedbackOS", layout="wide")

# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in to access the review queue.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

if user.get("role") not in ("ta", "instructor"):
    st.error("This page is only accessible to TAs and instructors.")
    st.stop()

ta_id = user["id"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "submitted": "🔵",
    "under_review": "🟡",
    "reviewed": "🟢",
    "resubmitted": "🟠",
}

STACK_BADGE_COLORS = {
    "streamlit": "#FF4B4B",
    "gradio": "#F97316",
    "flask": "#6366F1",
    "fastapi": "#10B981",
    "react": "#06B6D4",
    "openai": "#10A37F",
    "anthropic": "#D946EF",
}


def _fetch_submissions(
    status_filter: str | None = None,
    assignment_id: str | None = None,
) -> list[dict]:
    """Call the API and return a list of submission dicts."""
    params: dict = {"ta_id": ta_id}
    if status_filter and status_filter != "All":
        params["status"] = status_filter.lower().replace(" ", "_")
    if assignment_id:
        params["assignment_id"] = assignment_id

    try:
        resp = httpx.get(f"{FASTAPI_URL}/submissions", params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except httpx.HTTPStatusError as exc:
        st.error(f"API error: {exc.response.status_code} — {exc.response.text}")
        return []
    except httpx.RequestError as exc:
        st.error(f"Could not reach the API ({FASTAPI_URL}). Is the server running? Error: {exc}")
        return []


def _stack_badges(detected_stack: dict | None) -> str:
    """Build HTML stack badge string."""
    if not detected_stack:
        return ""
    tags = []
    for field in ("frontend", "backend", "llm_api"):
        val = (detected_stack.get(field) or "").lower()
        if val and val != "none" and val != "unknown":
            color = STACK_BADGE_COLORS.get(val, "#64748B")
            tags.append(
                f'<span style="background:{color};color:white;padding:2px 8px;'
                f'border-radius:12px;font-size:0.75rem;margin-right:4px">{val}</span>'
            )
    return "".join(tags)


def _time_ago(ts_str: str | None) -> str:
    if not ts_str:
        return "unknown"
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            return "< 1 hour ago"
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return ts_str[:10]


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.title("Review Queue")
st.caption(f"Showing submissions assigned to you ({user['name']})")

# ---------------------------------------------------------------------------
# Submit new repo form
# ---------------------------------------------------------------------------

with st.expander("➕ Submit a new repo for review", expanded=False):
    with st.form("ingest_form", clear_on_submit=True):
        repo_url_input = st.text_input(
            "GitHub repo URL",
            placeholder="https://github.com/student/project",
        )
        student_email_input = st.text_input(
            "Student email (optional — links submission to a student)",
            placeholder="priya@100x.test",
        )
        ingest_submitted = st.form_submit_button("Ingest & Submit", use_container_width=True)

    if ingest_submitted:
        if not repo_url_input:
            st.warning("Please enter a repo URL.")
        else:
            with st.spinner("Ingesting repo... this may take 20–40 seconds."):
                try:
                    resp = httpx.post(
                        f"{FASTAPI_URL}/submissions/ingest",
                        json={
                            "github_repo_url": repo_url_input,
                            "student_email": student_email_input or None,
                            "ta_email": user.get("email"),
                        },
                        timeout=120.0,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    st.success(
                        f"Repo ingested! `{result['submission_id'][:8]}...` "
                        f"({result['content_length']:,} chars)"
                    )
                    st.rerun()
                except httpx.HTTPStatusError as exc:
                    st.error(f"Failed ({exc.response.status_code}): {exc.response.text[:300]}")
                except Exception as exc:
                    st.error(f"Error: {exc}")

# Filters row
col_status, col_sort, col_refresh = st.columns([2, 2, 1])
with col_status:
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "Submitted", "Under Review", "Reviewed", "Resubmitted"],
        index=0,
    )
with col_sort:
    sort_by = st.selectbox(
        "Sort by",
        ["Newest first", "Oldest first", "Flagged first"],
        index=0,
    )
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    refresh = st.button("Refresh", use_container_width=True)

st.divider()

# Fetch data
with st.spinner("Loading submissions..."):
    submissions = _fetch_submissions(status_filter=status_filter)

if not submissions:
    st.info("No submissions found matching your filters.")
    st.stop()

# Sort
if sort_by == "Oldest first":
    submissions.sort(key=lambda s: s.get("created_at") or "")
elif sort_by == "Flagged first":
    submissions.sort(key=lambda s: (not s.get("is_flagged", False), s.get("created_at") or ""), reverse=False)
else:  # Newest first
    submissions.sort(key=lambda s: s.get("created_at") or "", reverse=True)

# Bring flagged to absolute top regardless of sort
flagged = [s for s in submissions if s.get("is_flagged")]
not_flagged = [s for s in submissions if not s.get("is_flagged")]
submissions = flagged + not_flagged

st.caption(f"{len(submissions)} submission(s)")

# Render cards
for sub in submissions:
    sub_id = sub.get("id", "")
    student = sub.get("student") or {}
    assignment = sub.get("assignment") or {}
    detected_stack = sub.get("detected_stack") or {}
    status = sub.get("status", "submitted")
    is_flagged = sub.get("is_flagged", False)

    student_name = student.get("name", "Unknown Student")
    project_title = assignment.get("title", "Untitled Project")
    status_dot = STATUS_COLORS.get(status, "⚪")
    submitted_ago = _time_ago(sub.get("submitted_at") or sub.get("created_at"))
    badges_html = _stack_badges(detected_stack)

    flag_indicator = "⚠️ FLAGGED — " if is_flagged else ""
    flag_note = sub.get("flag_note", "")

    with st.container(border=True):
        header_col, action_col = st.columns([5, 1])

        with header_col:
            st.markdown(
                f"**{flag_indicator}{student_name}** · {project_title} "
                f"{status_dot} `{status.replace('_', ' ').title()}`"
            )
            if badges_html:
                st.markdown(badges_html, unsafe_allow_html=True)
            st.caption(f"Submitted {submitted_ago}")
            if is_flagged and flag_note:
                st.warning(f"Flag note: {flag_note}")

        with action_col:
            if st.button("Review →", key=f"review_{sub_id}", use_container_width=True):
                st.session_state["selected_submission_id"] = sub_id
                st.session_state["selected_submission"] = sub
                st.switch_page("pages/2_Review.py")
