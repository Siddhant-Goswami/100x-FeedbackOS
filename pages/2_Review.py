"""
Review page — core TA review interface.

Two-column layout:
  Left:  Code viewer (file browser + syntax display)
  Right: Rubric scoring panel with AI assistance
"""

from __future__ import annotations

import os
import time
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

st.set_page_config(page_title="Review — FeedbackOS", layout="wide")

# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

if user.get("role") not in ("ta", "instructor"):
    st.error("This page is only accessible to TAs.")
    st.stop()

submission_id = st.session_state.get("selected_submission_id")
submission = st.session_state.get("selected_submission", {})

if not submission_id:
    st.warning("No submission selected. Go back to the Review Queue.")
    st.page_link("pages/1_Review_Queue.py", label="Back to Queue")
    st.stop()

ta_id = user["id"]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        resp = httpx.get(f"{FASTAPI_URL}{path}", params=params, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error on GET {path}: {exc}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    try:
        resp = httpx.post(f"{FASTAPI_URL}{path}", json=payload, timeout=20.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text[:300]}")
        return None
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# State initialization
# ---------------------------------------------------------------------------

if "review_id" not in st.session_state:
    result = api_post(
        "/reviews",
        {"submission_id": submission_id, "ta_id": ta_id},
    )
    if result:
        st.session_state["review_id"] = result["id"]
    else:
        st.error("Could not create/load review. Check API connection.")
        st.stop()

review_id = st.session_state["review_id"]

if "review_start_time" not in st.session_state:
    st.session_state["review_start_time"] = time.time()

if "scores" not in st.session_state:
    st.session_state["scores"] = {}  # dimension_id → {score, comment, action_item, source}

if "ai_suggestions" not in st.session_state:
    st.session_state["ai_suggestions"] = {}  # dimension_id → {suggested, reasoning}

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

assignment = submission.get("assignment") or {}
student = submission.get("student") or {}
assignment_id = assignment.get("id") or submission.get("assignment_id", "")

# Rubric dimensions
rubric_dims = api_get(f"/rubrics/{assignment_id}") or []

# Existing scores (resume in-progress review)
existing_scores = api_get(f"/reviews/{review_id}/scores") or []
for score_row in existing_scores:
    dim_id = score_row.get("dimension_id", "")
    if dim_id and dim_id not in st.session_state["scores"]:
        st.session_state["scores"][dim_id] = {
            "score": score_row.get("score", ""),
            "comment": score_row.get("comment", ""),
            "action_item": score_row.get("action_item", ""),
            "source": score_row.get("action_item_source", "ta_written"),
        }

# Submission files
sub_detail = api_get(f"/submissions/{submission_id}") or {}
files_list = sub_detail.get("files") or []

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Review Submission")
st.caption(
    f"Student: **{student.get('name', 'Unknown')}** · "
    f"Project: **{assignment.get('title', 'Unknown')}** · "
    f"Review ID: `{review_id[:8]}...`"
)

# Progress bar
scored_required = sum(
    1
    for d in rubric_dims
    if d.get("is_required") and d.get("id") in st.session_state["scores"]
)
total_required = sum(1 for d in rubric_dims if d.get("is_required"))
if total_required > 0:
    progress = scored_required / total_required
    st.progress(progress, text=f"Progress: {scored_required}/{total_required} required dimensions scored")

# Timer
elapsed = int(time.time() - st.session_state["review_start_time"])
mins, secs = divmod(elapsed, 60)
st.caption(f"Review time: {mins:02d}:{secs:02d}")

st.divider()

# ---------------------------------------------------------------------------
# Two-column layout
# ---------------------------------------------------------------------------

code_col, rubric_col = st.columns([1, 1], gap="large")

# ---- Left: Code viewer ----
with code_col:
    st.subheader("Code Viewer")
    repo_url = submission.get("github_repo_url") or sub_detail.get("github_repo_url", "")
    if repo_url:
        st.markdown(f"[Open on GitHub ↗]({repo_url})")

    # Check for gitingest content
    gitingest_tree = next(
        (f for f in files_list if f.get("filepath") == "_gitingest_tree"), None
    )
    gitingest_content = next(
        (f for f in files_list if f.get("filepath") == "_gitingest_content"), None
    )
    regular_files = [f for f in files_list if not f.get("filepath", "").startswith("_gitingest")]

    if gitingest_content:
        tree_tab, code_tab = st.tabs(["File Tree", "Full Code"])
        with tree_tab:
            st.code(
                gitingest_tree.get("content_preview", "") if gitingest_tree else "",
                language="text",
            )
        with code_tab:
            st.code(gitingest_content.get("content_preview", ""), language="text")

        # Store full content in session for AI suggestions
        st.session_state["repo_content"] = gitingest_content.get("content_preview", "")

    elif regular_files:
        file_paths = [f.get("filepath", "") for f in regular_files if f.get("filepath")]
        selected_file = st.selectbox("Browse files", ["(select a file)"] + file_paths)
        if selected_file and selected_file != "(select a file)":
            matching = [f for f in regular_files if f.get("filepath") == selected_file]
            if matching:
                preview = matching[0].get("content_preview") or "(No preview available)"
                ext = selected_file.rsplit(".", 1)[-1] if "." in selected_file else "text"
                lang_map = {"py": "python", "js": "javascript", "ts": "typescript",
                            "json": "json", "md": "markdown", "yml": "yaml", "yaml": "yaml",
                            "txt": "text", "sh": "bash", "html": "html", "css": "css"}
                st.code(preview, language=lang_map.get(ext.lower(), "text"))
    else:
        st.info("No code ingested yet. Use the Review Queue to submit the repo URL.")

# ---- Right: Rubric scoring ----
with rubric_col:
    st.subheader("Rubric")

    if not rubric_dims:
        st.warning("No rubric dimensions found for this assignment.")
    else:
        for dim in rubric_dims:
            dim_id = str(dim.get("id", ""))
            dim_name = dim.get("name", "Unknown")
            dim_desc = dim.get("description", "")
            is_required = dim.get("is_required", True)
            category = dim.get("category", "")

            current = st.session_state["scores"].get(dim_id, {})
            current_score = current.get("score", "")
            current_comment = current.get("comment", "")
            current_action = current.get("action_item", "")
            current_source = current.get("source", "ta_written")

            required_label = "✳ required" if is_required else "optional"
            with st.expander(
                f"{'✅' if current_score else '⬜'} **{dim_name}** · `{category}` · {required_label}",
                expanded=(not current_score),
            ):
                st.caption(dim_desc)

                # Examples
                examples_data = api_get(f"/examples/{dim_id}") or []
                if examples_data:
                    with st.expander("📚 See examples"):
                        for ex in examples_data[:3]:
                            score_label = ex.get("score", "").upper()
                            badge = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(score_label, "")
                            st.markdown(f"{badge} **{score_label}**: {ex.get('comment', '')}")
                            if ex.get("action_item"):
                                st.caption(f"Action: {ex['action_item']}")
                            if ex.get("was_acted_on"):
                                st.caption("✓ Student acted on this")
                            st.divider()

                # Score buttons
                score_cols = st.columns([1, 1, 1, 1, 1])
                score_map = {
                    0: ("green", "🟢 Green"),
                    1: ("yellow", "🟡 Yellow"),
                    2: ("red", "🔴 Red"),
                    3: ("not_applicable", "N/A"),
                    4: ("flagged_for_help", "🚩 Flag"),
                }

                for col_idx, (score_val, score_label) in score_map.items():
                    is_active = current_score == score_val
                    button_type = "primary" if is_active else "secondary"
                    if score_cols[col_idx].button(
                        score_label,
                        key=f"score_{dim_id}_{score_val}",
                        use_container_width=True,
                        type=button_type,
                    ):
                        if score_val == "flagged_for_help":
                            # Flag via dedicated endpoint
                            api_post(
                                f"/reviews/{review_id}/flag-for-help",
                                {"dimension_id": dim_id, "note": ""},
                            )
                        else:
                            api_post(
                                f"/reviews/{review_id}/scores",
                                {
                                    "dimension_id": dim_id,
                                    "score": score_val,
                                    "comment": current_comment,
                                    "action_item": current_action,
                                    "action_item_source": current_source,
                                },
                            )
                        st.session_state["scores"].setdefault(dim_id, {})["score"] = score_val
                        st.rerun()

                # Comment + action item (shown for yellow/red)
                if current_score in ("yellow", "red"):
                    new_comment = st.text_area(
                        "Comment",
                        value=current_comment,
                        key=f"comment_{dim_id}",
                        placeholder="Explain what the issue is and where to find it...",
                        height=80,
                    )

                    # AI action item suggestion
                    ai_col, skip_col = st.columns([2, 1])
                    with ai_col:
                        if st.button(
                            "✨ Suggest action item (AI)",
                            key=f"suggest_{dim_id}",
                            use_container_width=True,
                        ):
                            with st.spinner("Thinking..."):
                                repo_content = st.session_state.get("repo_content", "")
                                payload = {
                                    "dimension_id": dim_id,
                                    "score": current_score,
                                    "code_snippet": repo_content[:3000],
                                    "context": new_comment,
                                }
                                suggestion = api_post(
                                    f"/reviews/{review_id}/suggest-action", payload
                                )
                                if suggestion:
                                    st.session_state["ai_suggestions"][dim_id] = suggestion

                    suggestion = st.session_state["ai_suggestions"].get(dim_id)
                    if suggestion:
                        st.info(f"**AI suggests:** {suggestion.get('suggested_action_item', '')}")
                        st.caption(f"Reasoning: {suggestion.get('reasoning', '')}")

                        accept_col, edit_col = st.columns(2)
                        with accept_col:
                            if st.button("Accept", key=f"accept_{dim_id}"):
                                new_action = suggestion["suggested_action_item"]
                                st.session_state["scores"].setdefault(dim_id, {})[
                                    "action_item"
                                ] = new_action
                                st.session_state["scores"][dim_id]["source"] = "ai_suggested_accepted"
                                api_post(
                                    f"/reviews/{review_id}/scores",
                                    {
                                        "dimension_id": dim_id,
                                        "score": current_score,
                                        "comment": new_comment,
                                        "action_item": new_action,
                                        "action_item_source": "ai_suggested_accepted",
                                    },
                                )
                                del st.session_state["ai_suggestions"][dim_id]
                                st.rerun()

                    new_action = st.text_area(
                        "Action item",
                        value=current_action,
                        key=f"action_{dim_id}",
                        placeholder="What specific step should the student take?",
                        height=80,
                    )

                    # Save comment + action item on change
                    if new_comment != current_comment or new_action != current_action:
                        source = "ai_suggested_edited" if suggestion else "ta_written"
                        st.session_state["scores"].setdefault(dim_id, {}).update(
                            {
                                "comment": new_comment,
                                "action_item": new_action,
                                "source": source,
                            }
                        )
                        api_post(
                            f"/reviews/{review_id}/scores",
                            {
                                "dimension_id": dim_id,
                                "score": current_score,
                                "comment": new_comment,
                                "action_item": new_action,
                                "action_item_source": source,
                            },
                        )

# ---------------------------------------------------------------------------
# Submit button
# ---------------------------------------------------------------------------

st.divider()
submit_col, back_col = st.columns([1, 1])

with back_col:
    if st.button("← Back to Queue", use_container_width=True):
        st.switch_page("pages/1_Review_Queue.py")

with submit_col:
    if st.button("Submit Review ✓", type="primary", use_container_width=True):
        with st.spinner("Validating and submitting..."):
            result = api_post(f"/reviews/{review_id}/submit", {})
            if result:
                st.success("Review submitted! The student has been notified.")
                # Clear review state
                for key in ["review_id", "scores", "ai_suggestions", "review_start_time",
                            "selected_submission_id", "selected_submission"]:
                    st.session_state.pop(key, None)
                time.sleep(1.5)
                st.switch_page("pages/1_Review_Queue.py")
