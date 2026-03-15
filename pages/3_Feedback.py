"""
Feedback page — student view.

Reads review_id from query params (?review_id=...) and displays
the student's feedback in a clean, prioritized format.
"""

from __future__ import annotations

import os

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

st.set_page_config(page_title="Your Feedback — FeedbackOS", layout="centered")

# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in to view your feedback.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

# ---------------------------------------------------------------------------
# Read review_id from query params
# ---------------------------------------------------------------------------

params = st.query_params
review_id = params.get("review_id")

if not review_id:
    st.title("Your Feedback")
    st.info("No review ID provided. Check your DM from the FeedbackOS bot for your personal link.")
    st.stop()

# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------


def api_get(path: str) -> dict | list | None:
    try:
        resp = httpx.get(f"{FASTAPI_URL}{path}", timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Could not load feedback: {exc}")
        return None


scores = api_get(f"/reviews/{review_id}/scores")
if scores is None:
    st.stop()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCORE_ICONS = {
    "green": ("🟢", "Looks Great", "#D1FAE5"),
    "yellow": ("🟡", "Needs Improvement", "#FEF3C7"),
    "red": ("🔴", "Must Fix", "#FEE2E2"),
    "not_applicable": ("⚪", "Not Applicable", "#F1F5F9"),
    "flagged_for_help": ("🚩", "Flagged for Help", "#FDF4FF"),
}

# Sort scores: red first, then yellow, then others
priority_order = {"red": 0, "yellow": 1, "flagged_for_help": 2, "green": 3, "not_applicable": 4}
scores_sorted = sorted(
    scores,
    key=lambda s: priority_order.get(s.get("score", ""), 99),
)

# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.title("Your Feedback")
st.caption(f"Review ID: `{review_id}`")
st.divider()

# Quick summary counts
reds = [s for s in scores if s.get("score") == "red"]
yellows = [s for s in scores if s.get("score") == "yellow"]
greens = [s for s in scores if s.get("score") == "green"]

summary_col1, summary_col2, summary_col3 = st.columns(3)
with summary_col1:
    st.metric("Must Fix 🔴", len(reds))
with summary_col2:
    st.metric("Improve 🟡", len(yellows))
with summary_col3:
    st.metric("Great Work 🟢", len(greens))

st.divider()

# ---- Prioritized action items ----
action_items = [
    s for s in scores_sorted
    if s.get("action_item") and s.get("score") in ("red", "yellow")
]

if action_items:
    st.subheader("What to do next")
    st.caption("Work through these in order — red items first.")

    for i, score_row in enumerate(action_items, 1):
        score = score_row.get("score", "")
        icon, label, bg = SCORE_ICONS.get(score, ("⬜", score, "#FFFFFF"))
        dim = score_row.get("dimension") or {}
        dim_name = dim.get("name") if dim else score_row.get("dimension_id", "")

        st.markdown(
            f"""
            <div style="background:{bg};border-radius:8px;padding:12px 16px;margin-bottom:8px">
                <strong>{i}. {icon} {dim_name}</strong><br>
                {score_row.get('action_item', '')}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

# ---- Per-dimension detail cards ----
st.subheader("Full Feedback")

for score_row in scores_sorted:
    score = score_row.get("score", "")
    icon, label, bg = SCORE_ICONS.get(score, ("⬜", score, "#FFFFFF"))
    dim = score_row.get("dimension") or {}
    dim_name = dim.get("name") if dim else score_row.get("dimension_id", "Unknown Dimension")
    comment = score_row.get("comment") or ""
    action_item = score_row.get("action_item") or ""

    with st.container(border=True):
        st.markdown(f"**{icon} {dim_name}** — {label}")
        if comment:
            st.write(comment)
        if action_item:
            st.info(f"**Action:** {action_item}")
        if not comment and not action_item and score == "green":
            st.caption("No specific comments — keep it up!")

st.divider()

# ---- Discord thread link ----
st.subheader("Questions?")
st.write(
    "If you have questions about your feedback, reach out in your feedback thread on Discord. "
    "Your TA will be notified."
)
discord_thread_name = f"feedback-{review_id}"
st.info(
    f"Look for a Discord thread named: **{discord_thread_name}**\n\n"
    "If the thread hasn't been created yet, ask your TA to open one."
)
