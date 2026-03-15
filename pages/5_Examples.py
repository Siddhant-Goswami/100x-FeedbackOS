"""
Examples page — browse curated example feedback entries.

Filterable by dimension and tech stack.
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

st.set_page_config(page_title="Examples — FeedbackOS", layout="wide")

# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_get(path: str, params: dict | None = None) -> dict | None:
    try:
        resp = httpx.get(f"{FASTAPI_URL}{path}", params=params, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


SCORE_ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.title("Example Feedback Library")
st.caption("Browse real examples of high-quality feedback across all rubric dimensions.")
st.divider()

# Load all examples grouped by dimension
with st.spinner("Loading examples..."):
    data = api_get("/examples")

if not data:
    st.error("Could not load examples.")
    st.stop()

examples_by_dim: dict[str, list] = data.get("examples", {})
total = data.get("total", 0)

if not examples_by_dim:
    st.info("No examples have been seeded yet. Run `python scripts/seed_examples.py`.")
    st.stop()

# Build dimension name → id map and filter options
all_dims: dict[str, str] = {}  # name → dim_id
stack_tags: set[str] = set()

for dim_id, ex_list in examples_by_dim.items():
    for ex in ex_list:
        dim = ex.get("dimension") or {}
        if dim.get("name"):
            all_dims[dim["name"]] = dim_id
        tag = ex.get("stack_tag")
        if tag:
            stack_tags.add(tag)

# Filters
filter_col1, filter_col2, filter_col3 = st.columns([3, 2, 2])

with filter_col1:
    dim_options = ["All Dimensions"] + sorted(all_dims.keys())
    selected_dim_name = st.selectbox("Filter by dimension", dim_options)

with filter_col2:
    stack_options = ["All Stacks"] + sorted(stack_tags)
    selected_stack = st.selectbox("Filter by stack", stack_options)

with filter_col3:
    score_options = ["All Scores", "Green", "Yellow", "Red"]
    selected_score = st.selectbox("Filter by score", score_options)

st.divider()
st.caption(f"{total} total example(s)")

# Apply filters and render
shown = 0

for dim_name in sorted(all_dims.keys()):
    if selected_dim_name != "All Dimensions" and dim_name != selected_dim_name:
        continue

    dim_id = all_dims[dim_name]
    examples = examples_by_dim.get(dim_id, [])

    # Apply stack and score filters
    filtered = []
    for ex in examples:
        if selected_stack != "All Stacks":
            tag = ex.get("stack_tag") or ""
            if tag and tag.lower() != selected_stack.lower():
                continue
        if selected_score != "All Scores":
            if ex.get("score", "").lower() != selected_score.lower():
                continue
        filtered.append(ex)

    if not filtered:
        continue

    st.subheader(dim_name)
    for ex in filtered:
        score = ex.get("score", "")
        icon = SCORE_ICON.get(score, "⬜")
        comment = ex.get("comment", "")
        action = ex.get("action_item") or ""
        was_acted = ex.get("was_acted_on", False)
        stack_tag = ex.get("stack_tag") or "universal"

        with st.container(border=True):
            header_row = st.columns([1, 6, 2])
            header_row[0].markdown(f"## {icon}")
            header_row[1].markdown(f"**{comment}**")
            header_row[2].caption(f"`{stack_tag}`")
            if was_acted:
                header_row[2].markdown("✅ Student acted on this")

            if action:
                st.info(f"**Suggested action:** {action}")

        shown += 1

if shown == 0:
    st.info("No examples match the selected filters.")
